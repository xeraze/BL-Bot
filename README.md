<div align="center">

# BL-Bot

### ApplicationBoy alternative

![BL Bot Embed Example](assets/blbot-embed.svg)

A Python Discord bot developed as an open-source alternative to ApplicationBoy.

</div>

---

## Overview

![BL Bot VS ApplicationBoy](assets/blbot_vs_applicationboy.svg)

**BL-Bot** posts vacancies as embeds in any channel, accepts applications
through modals, and lets staff review candidates (accept / reject / request
info / start a dialogue) right under the vacancy message. Candidate and
reviewer can talk in a thread that is mirrored to the candidate's DMs.

## Commands

| Command | Who | Description |
| --- | --- | --- |
| `/bl работа` | everyone | List open vacancies and apply |
| `/bl идея` | everyone | Submit an idea for review |
| `/bl новости` | `ROLE_NEWS` | Publish a news embed to the current channel |
| `/bl дработа` | `ROLE_JOBS_MANAGE` | Add a vacancy (staged, not published) |
| `/bl уработа` | `ROLE_JOBS_MANAGE` | Remove a vacancy |

## Tech Stack

- Python 3.10+
- [discord.py](https://github.com/Rapptz/discord.py) 2.x (app commands, UI kits)
- python-dotenv
- JSON files as storage (`data/`, git-ignored — created automatically)

No database, no external services.

## Setup

1. Clone the repository and create a virtual environment:

   ```bash
   git clone https://github.com/xeraze/BL-Bot.git
   cd BL-Bot
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root (see `.env.example` values below):

   | Variable | Required | Description |
   | --- | --- | --- |
   | `DISCORD_TOKEN` | yes | Bot token |
   | `GUILD_ID` | recommended | Server ID — syncs slash commands instantly (without it global sync can take up to an hour) |
   | `APPLICATIONS_CHANNEL_ID` | yes | Channel where application embeds are posted |
   | `ERROR_LOG_CHANNEL_ID` | no | Channel for error reports |
   | `ROLE_NEWS` | for `/bl новости` | Role allowed to publish news |
   | `ROLE_JOBS_MANAGE` | for `/bl дработа`, `/bl уработа` | Role allowed to manage vacancies and review applications |
   | `IDEA_REVIEW_CHANNEL_ID` | for `/bl идея` | Staff channel where ideas are reviewed |
   | `IDEA_PUBLIC_CHANNEL_ID` | no | Channel for approved ideas (auto-posted with 👍/👎) |
   | `IDEA_APPROVER_ROLE_ID` | for idea review | Role allowed to accept/reject ideas |

   Leave an empty value (or a placeholder like `ROLE_ID_HERE`) to **disable**
   the related command for everyone — commands fail safe by default.

3. In the [Discord Developer Portal](https://discord.com/developers/applications)
   enable the **Message Content Intent** (Bot → Privileged Gateway Intents),
   then invite the bot with `bot` and `applications.commands` scopes.

4. Run:

   ```bash
   python main.py
   ```

## Project Structure

```text
BL-Bot/
├── cogs/           Bot modules (bl.py — commands & ideas, reviews.py — applications)
├── utils/          Storage, permissions, error logging helpers
├── data/           Runtime data (git-ignored, created on first write)
├── assets/         Screenshots and mockups for this README
├── main.py         Entry point
├── requirements.txt
└── .gitignore
```

## License

[MIT](LICENSE) — fork it, modify it, use it for any purpose, including
commercial. Third-party logos remain property of their owners.

---

<div align="center">

Developed by **xeraze**

</div>
