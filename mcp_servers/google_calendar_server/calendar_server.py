"""
Google Calendar Server MCP Server

Implements secure Google Calendar integration with OAuth 2.0 authentication
for event management, availability checking, and automated meeting scheduling.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

# Add Django project to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

try:
    import django
    django.setup()
    from django.contrib.auth.models import User
    from ecomapp.models import Event
except ImportError:
    # Handle case where Django is not available
    pass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..base_mcp_server import BaseMCPServer, MCPServerError, MCPAuthenticationError

logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Calendar configuration
CALENDAR_ID = 'primary'  # Use primary calendar by default


class GoogleCalendarServer(BaseMCPServer):
    """
    Google Calendar Server MCP Server
    
    Provides secure Google Calendar integration with OAuth 2.0 authentication.
    Handles event creation, modification, deletion, and availability checking
    with automatic Google Meet link generation for meetings.
    """
    
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        super().__init__("Google Calendar Server", "1.0.0")
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Calendar API using OAuth 2.0"""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            except Exception as e:
                logger.warning(f"Could not load existing token: {e}")
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Could not refresh token: {e}")
                    creds = None
            
            if not creds:
                if os.path.exists(self.credentials_file):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES)
                    creds = flow.run_local_server(port=0)
                else:
                    logger.warning(f"Credentials file {self.credentials_file} not found")
                    return
            
            # Save the credentials for the next run
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                logger.error(f"Could not save token: {e}")
        
        # Build the service
        try:
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Successfully authenticated with Google Calendar API")
        except Exception as e:
            logger.error(f"Could not build Google Calendar service: {e}")
            self.service = None
    
    def _initialize_tools(self):
        """Initialize Google Calendar tools"""
        
        # Create Event Tool
        self.register_tool(
            name="calendar_create_event",
            description="Create a new calendar event with optional Google Meet link",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "title": {"type": "string", "description": "Event title"},
                    "description": {"type": "string", "description": "Event description"},
                    "start_datetime": {"type": "string", "format": "date-time", "description": "Start datetime (ISO format)"},
                    "end_datetime": {"type": "string", "format": "date-time", "description": "End datetime (ISO format)"},
                    "attendees": {"type": "array", "items": {"type": "string", "format": "email"}, "description": "Attendee email addresses"},
                    "is_meeting": {"type": "boolean", "default": False, "description": "Whether to generate Google Meet link"},
                    "deadline_type": {"type": "string", "enum": ["TAX_PAYMENT", "INVOICE_DUE", "LOAN_REPAYMENT", "MEETING", "REMINDER", "OTHER"]},
                    "amount": {"type": "number", "description": "Associated amount if applicable"},
                    "reminder_minutes": {"type": "integer", "default": 15, "description": "Reminder time in minutes"}
                },
                "required": ["merchant_id", "title", "start_datetime", "end_datetime"]
            }
        )
        
        # Find Events Tool
        self.register_tool(
            name="calendar_find_events",
            description="Find calendar events with filters",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "start_date": {"type": "string", "format": "date", "description": "Start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "format": "date", "description": "End date (YYYY-MM-DD)"},
                    "query": {"type": "string", "description": "Search query for event titles/descriptions"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 250, "default": 10}
                },
                "required": ["merchant_id"]
            }
        )
        
        # Update Event Tool
        self.register_tool(
            name="calendar_update_event",
            description="Update an existing calendar event",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "event_id": {"type": "string", "description": "Google Calendar event ID"},
                    "title": {"type": "string", "description": "Updated event title"},
                    "description": {"type": "string", "description": "Updated event description"},
                    "start_datetime": {"type": "string", "format": "date-time", "description": "Updated start datetime"},
                    "end_datetime": {"type": "string", "format": "date-time", "description": "Updated end datetime"},
                    "attendees": {"type": "array", "items": {"type": "string", "format": "email"}},
                    "status": {"type": "string", "enum": ["UPCOMING", "COMPLETED", "CANCELLED"]}
                },
                "required": ["merchant_id", "event_id"]
            }
        )
        
        # Delete Event Tool
        self.register_tool(
            name="calendar_delete_event",
            description="Delete a calendar event",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "event_id": {"type": "string", "description": "Google Calendar event ID"},
                    "send_notifications": {"type": "boolean", "default": True, "description": "Send cancellation notifications"}
                },
                "required": ["merchant_id", "event_id"]
            }
        )
        
        # Check Availability Tool
        self.register_tool(
            name="calendar_check_availability",
            description="Check calendar availability for a time slot",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "start_datetime": {"type": "string", "format": "date-time", "description": "Start datetime to check"},
                    "end_datetime": {"type": "string", "format": "date-time", "description": "End datetime to check"},
                    "attendees": {"type": "array", "items": {"type": "string", "format": "email"}, "description": "Attendee emails to check availability"}
                },
                "required": ["merchant_id", "start_datetime", "end_datetime"]
            }
        )
        
        # Get Free Time Tool
        self.register_tool(
            name="calendar_get_free_time",
            description="Find free time slots in calendar",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "date": {"type": "string", "format": "date", "description": "Date to check (YYYY-MM-DD)"},
                    "duration_minutes": {"type": "integer", "minimum": 15, "default": 60, "description": "Duration in minutes"},
                    "business_hours_only": {"type": "boolean", "default": True, "description": "Only show business hours (9 AM - 5 PM)"}
                },
                "required": ["merchant_id", "date"]
            }
        )
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Google Calendar tools"""
        
        if not self.service:
            raise MCPServerError("Google Calendar service not available. Please check authentication.")
        
        try:
            if tool_name == "calendar_create_event":
                return await self._create_event(arguments)
            elif tool_name == "calendar_find_events":
                return await self._find_events(arguments)
            elif tool_name == "calendar_update_event":
                return await self._update_event(arguments)
            elif tool_name == "calendar_delete_event":
                return await self._delete_event(arguments)
            elif tool_name == "calendar_check_availability":
                return await self._check_availability(arguments)
            elif tool_name == "calendar_get_free_time":
                return await self._get_free_time(arguments)
            else:
                raise MCPServerError(f"Unknown tool: {tool_name}")
                
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            raise MCPServerError(f"Google Calendar API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error executing calendar tool {tool_name}: {e}")
            raise MCPServerError(f"Calendar operation failed: {str(e)}")
    
    async def _create_event(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new calendar event"""
        merchant_id = args["merchant_id"]
        title = args["title"]
        description = args.get("description", "")
        start_datetime = args["start_datetime"]
        end_datetime = args["end_datetime"]
        attendees = args.get("attendees", [])
        is_meeting = args.get("is_meeting", False)
        deadline_type = args.get("deadline_type", "OTHER")
        amount = args.get("amount")
        reminder_minutes = args.get("reminder_minutes", 15)
        
        # Verify merchant exists
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Parse datetime strings
        start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_datetime.replace('Z', '+00:00'))
        
        # Build event object
        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': reminder_minutes},
                    {'method': 'popup', 'minutes': reminder_minutes},
                ],
            },
        }
        
        # Add attendees if provided
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        
        # Add Google Meet link if it's a meeting
        if is_meeting:
            event['conferenceData'] = {
                'createRequest': {
                    'requestId': f"meet_{merchant_id}_{int(start_dt.timestamp())}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
        
        # Create the event
        try:
            created_event = self.service.events().insert(
                calendarId=CALENDAR_ID,
                body=event,
                conferenceDataVersion=1 if is_meeting else 0
            ).execute()
        except HttpError as e:
            if e.resp.status == 403:
                raise MCPAuthenticationError("Insufficient permissions to create calendar events")
            raise
        
        # Store in local database for synchronization
        try:
            local_event = Event.objects.create(
                merchant=merchant,
                title=title,
                description=description,
                event_date=start_dt,
                deadline_type=deadline_type,
                amount=amount,
                calendar_id=created_event['id'],
                status='UPCOMING'
            )
        except Exception as e:
            logger.warning(f"Could not store event in local database: {e}")
        
        # Extract Google Meet link if available
        meet_link = None
        if is_meeting and 'conferenceData' in created_event:
            meet_link = created_event['conferenceData'].get('entryPoints', [{}])[0].get('uri')
        
        return {
            "event_created": {
                "id": created_event['id'],
                "title": created_event['summary'],
                "start_datetime": created_event['start']['dateTime'],
                "end_datetime": created_event['end']['dateTime'],
                "meet_link": meet_link,
                "html_link": created_event.get('htmlLink'),
                "status": created_event.get('status')
            },
            "local_event_id": local_event.id if 'local_event' in locals() else None,
            "created_at": datetime.now().isoformat()
        }
    
    async def _find_events(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Find calendar events with filters"""
        merchant_id = args["merchant_id"]
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        query = args.get("query", "")
        max_results = args.get("max_results", 10)
        
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Build time range filter
        time_min = None
        time_max = None
        if start_date:
            time_min = f"{start_date}T00:00:00Z"
        if end_date:
            time_max = f"{end_date}T23:59:59Z"
        
        # Query events
        try:
            events_result = self.service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                q=query,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
        except HttpError as e:
            if e.resp.status == 403:
                raise MCPAuthenticationError("Insufficient permissions to access calendar")
            raise
        
        events = events_result.get('items', [])
        
        # Format results
        formatted_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Extract Google Meet link if available
            meet_link = None
            if 'conferenceData' in event:
                meet_link = event['conferenceData'].get('entryPoints', [{}])[0].get('uri')
            
            formatted_events.append({
                "id": event['id'],
                "title": event['summary'],
                "description": event.get('description', ''),
                "start_datetime": start,
                "end_datetime": end,
                "status": event.get('status'),
                "meet_link": meet_link,
                "attendees": [attendee.get('email') for attendee in event.get('attendees', [])],
                "html_link": event.get('htmlLink')
            })
        
        return {
            "events": formatted_events,
            "total_found": len(formatted_events),
            "search_criteria": {
                "start_date": start_date,
                "end_date": end_date,
                "query": query,
                "max_results": max_results
            }
        }
    
    async def _update_event(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing calendar event"""
        merchant_id = args["merchant_id"]
        event_id = args["event_id"]
        
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Get existing event
        try:
            existing_event = self.service.events().get(
                calendarId=CALENDAR_ID,
                eventId=event_id
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                raise MCPServerError(f"Event {event_id} not found")
            elif e.resp.status == 403:
                raise MCPAuthenticationError("Insufficient permissions to update event")
            raise
        
        # Update fields
        if "title" in args:
            existing_event['summary'] = args["title"]
        if "description" in args:
            existing_event['description'] = args["description"]
        if "start_datetime" in args:
            start_dt = datetime.fromisoformat(args["start_datetime"].replace('Z', '+00:00'))
            existing_event['start'] = {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            }
        if "end_datetime" in args:
            end_dt = datetime.fromisoformat(args["end_datetime"].replace('Z', '+00:00'))
            existing_event['end'] = {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            }
        if "attendees" in args:
            existing_event['attendees'] = [{'email': email} for email in args["attendees"]]
        
        # Update the event
        try:
            updated_event = self.service.events().update(
                calendarId=CALENDAR_ID,
                eventId=event_id,
                body=existing_event
            ).execute()
        except HttpError as e:
            if e.resp.status == 403:
                raise MCPAuthenticationError("Insufficient permissions to update event")
            raise
        
        # Update local database
        try:
            local_event = Event.objects.get(calendar_id=event_id)
            if "title" in args:
                local_event.title = args["title"]
            if "description" in args:
                local_event.description = args["description"]
            if "start_datetime" in args:
                local_event.event_date = datetime.fromisoformat(args["start_datetime"].replace('Z', '+00:00'))
            if "status" in args:
                local_event.status = args["status"]
            local_event.save()
        except Event.DoesNotExist:
            logger.warning(f"Local event not found for calendar ID {event_id}")
        except Exception as e:
            logger.warning(f"Could not update local event: {e}")
        
        return {
            "event_updated": {
                "id": updated_event['id'],
                "title": updated_event['summary'],
                "start_datetime": updated_event['start']['dateTime'],
                "end_datetime": updated_event['end']['dateTime'],
                "status": updated_event.get('status')
            },
            "updated_at": datetime.now().isoformat()
        }
    
    async def _delete_event(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a calendar event"""
        merchant_id = args["merchant_id"]
        event_id = args["event_id"]
        send_notifications = args.get("send_notifications", True)
        
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Delete from Google Calendar
        try:
            self.service.events().delete(
                calendarId=CALENDAR_ID,
                eventId=event_id,
                sendNotifications=send_notifications
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                raise MCPServerError(f"Event {event_id} not found")
            elif e.resp.status == 403:
                raise MCPAuthenticationError("Insufficient permissions to delete event")
            raise
        
        # Update local database
        try:
            local_event = Event.objects.get(calendar_id=event_id)
            local_event.status = 'CANCELLED'
            local_event.save()
        except Event.DoesNotExist:
            logger.warning(f"Local event not found for calendar ID {event_id}")
        except Exception as e:
            logger.warning(f"Could not update local event: {e}")
        
        return {
            "event_deleted": {
                "id": event_id,
                "deleted_at": datetime.now().isoformat()
            }
        }
    
    async def _check_availability(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Check calendar availability for a time slot"""
        merchant_id = args["merchant_id"]
        start_datetime = args["start_datetime"]
        end_datetime = args["end_datetime"]
        attendees = args.get("attendees", [])
        
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Parse datetime strings
        start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_datetime.replace('Z', '+00:00'))
        
        # Check for conflicts
        try:
            events_result = self.service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
        except HttpError as e:
            if e.resp.status == 403:
                raise MCPAuthenticationError("Insufficient permissions to check availability")
            raise
        
        conflicting_events = events_result.get('items', [])
        is_available = len(conflicting_events) == 0
        
        return {
            "availability": {
                "is_available": is_available,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
                "conflicting_events": [
                    {
                        "id": event['id'],
                        "title": event['summary'],
                        "start": event['start'].get('dateTime', event['start'].get('date')),
                        "end": event['end'].get('dateTime', event['end'].get('date'))
                    }
                    for event in conflicting_events
                ],
                "conflict_count": len(conflicting_events)
            }
        }
    
    async def _get_free_time(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Find free time slots in calendar"""
        merchant_id = args["merchant_id"]
        date = args["date"]
        duration_minutes = args.get("duration_minutes", 60)
        business_hours_only = args.get("business_hours_only", True)
        
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Parse date and set time boundaries
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        
        if business_hours_only:
            start_time = date_obj.replace(hour=9, minute=0, second=0)
            end_time = date_obj.replace(hour=17, minute=0, second=0)
        else:
            start_time = date_obj.replace(hour=0, minute=0, second=0)
            end_time = date_obj.replace(hour=23, minute=59, second=59)
        
        # Get events for the day
        try:
            events_result = self.service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
        except HttpError as e:
            if e.resp.status == 403:
                raise MCPAuthenticationError("Insufficient permissions to check free time")
            raise
        
        events = events_result.get('items', [])
        
        # Calculate free time slots
        free_slots = []
        current_time = start_time
        
        for event in events:
            event_start = datetime.fromisoformat(
                event['start'].get('dateTime', event['start'].get('date')).replace('Z', '+00:00')
            )
            
            # Check if there's a gap before this event
            if event_start > current_time:
                gap_duration = (event_start - current_time).total_seconds() / 60
                if gap_duration >= duration_minutes:
                    free_slots.append({
                        "start_datetime": current_time.isoformat(),
                        "end_datetime": event_start.isoformat(),
                        "duration_minutes": gap_duration
                    })
            
            # Update current time to end of this event
            event_end = datetime.fromisoformat(
                event['end'].get('dateTime', event['end'].get('date')).replace('Z', '+00:00')
            )
            current_time = max(current_time, event_end)
        
        # Check for free time after the last event
        if current_time < end_time:
            gap_duration = (end_time - current_time).total_seconds() / 60
            if gap_duration >= duration_minutes:
                free_slots.append({
                    "start_datetime": current_time.isoformat(),
                    "end_datetime": end_time.isoformat(),
                    "duration_minutes": gap_duration
                })
        
        return {
            "free_time_slots": free_slots,
            "date": date,
            "duration_minutes": duration_minutes,
            "business_hours_only": business_hours_only,
            "total_free_slots": len(free_slots)
        }


# Server instance for running
calendar_server = GoogleCalendarServer()


if __name__ == "__main__":
    import asyncio
    import json
    
    async def main():
        # Example usage
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "calendar_create_event",
                "arguments": {
                    "merchant_id": 1,
                    "title": "Test Meeting",
                    "description": "Test meeting created by MCP server",
                    "start_datetime": "2024-01-15T10:00:00Z",
                    "end_datetime": "2024-01-15T11:00:00Z",
                    "is_meeting": True
                }
            },
            "id": 1
        }
        
        response = await calendar_server.handle_request(request)
        print(json.dumps(response.data, indent=2, default=str))
    
    asyncio.run(main())
