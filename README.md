# omelettePy

A Discord Utility bot, by [Charlotte](https://github.com/charlotte-2222)

<img src="https://raw.githubusercontent.com/charlotte-2222/charlotte-2222/32de06aa5256b8f3fbee5de105ce485d1bf8f360/trans-rights.svg">

![GitHub release (latest by date)](https://img.shields.io/github/v/release/charlotte-2222/omelettePy)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/charlotte-2222/omelettePy)

## Features

- **Database(s)**
  - asyncpg/PostgreSQL database for tags and reminders.
    - Tags allow users to create and store large amounts of text, and retrieve them later.
    - Reminders is simply task scheduling. Allows for storing timezones and "human" time conversion.
  - Sqlite3 DB for quotes.
    - Quotes are a simple way to store and retrieve quotes. This is more of a fun thing, thus sqlite3 is used.

- **GitHub Integration**
  - Allows for easy access to GitHub repositories and issues.
  - Allows for easy access to GitHub Gists.
  - Allows for easy access to GitHub Actions.

- **Weather**
  - Allows for easy access to weather information.
  - Allows for easy access to weather forecasts.
  - Allows for easy access to weather alerts.

- **RTFM (Read the fucking manual)**
  - If users ask silly questions without reading documentation, this links to specifc locations in the documentation.
  - Page Types:
    - Discord.py (stable, latest)
    - Python
    - Discord.py, Japanese (stable, latest)
    - Python, Japanese (stable, latest)
- **GUI**
  - A rather simple gui using a rather complex library (PyQt6).
  - Allows for real-time monitoring of the bot, resources, and other miscellaneous things.
  - Logging and debugging.
  - Looks nice and is fun but is overall not needed for greater function.

# Installation

I would recommend not running your own instance of this bot, it can be a pain to set up and maintain.

1. Python 3.8 or higher is required

this is a requirement for the bot to run, and is not optional.

2. Setup a virtual environment

`python3.8 -m venv venv`

3. Install dependencies

`pip install -U -r requirements.txt`

4. Create the database in PostgreSQL

You will need PostgreSQL installed and running.

Migrations should run automatically for database setup (tables, etc)., but you can run them manually if needed via
migrations folder.

5. Setup config.py

An example config.py is provided in the repository. You will need to fill in the values for your bot.

---
That should be it for basic setup, I recommend using PyCharm is it will take care of most of the work.

## Privacy Policy and Terms of Service

I am required by discord to create this.

This bot does not store sensitive or personal user information.



