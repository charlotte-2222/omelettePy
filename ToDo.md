# Feature ToDo List

*This is a simple todo list for brainstorming new implementations*

- [X] Reminder Functions
    - Store reminders in SQLite3 DB, fields like `user_id`, `reminder_text`, `time_to_trigger`, `channel_id`
    - Use Discord.ext.tasks and/or asyncio to check periodically for reminders that are due and send them (Prob via DM?)
    - Allow users to list, edit, delete existing reminders.
    - Example Commands:
        - `/reminder add "whatever reminder event" at <time/date>`
        - `/reminder list`
        - `/reminder delete 3`

- [ ] Google Calender Integration
    - Will need to use [Google Calendar API](https://developers.google.com/calendar/api/guides/overview)
    - Let users sync their reminders or fetch events
    - OAuth2 will be necessary for authentication, can be implemented for personal accounts or allow user to authorize
      their accounts via flow
    - Example commands:
        - `/calendar events upcoming`
        - `/calendar add "whatever calendar event" at <time/date>`

- [ ] Light ChatGPT Integration
    - Focus on utility-based use cases like:
        - Summary of articles
        - Generating quick code snippets/explaining code
    - Limit interaction to ensure focused use:
        - `/ai summarize "Paragraph"`
        - `/ai suggest-tags "example text for github issue"`
    - Implement command-specific tokens or rate-limits to avoid misuse

***Misc. Tasks:***

- Design database schema
- Design API workflows.