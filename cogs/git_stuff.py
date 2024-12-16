import traceback

import discord
import requests
from discord import app_commands
from discord.ext import commands

from utilFunc.config import GITHUB_TOKEN


class CreateIssue(discord.ui.Modal, title='Create New Issue'):
    name = discord.ui.TextInput(label='Issue Name',
                                required=True,
                                max_length=100,
                                min_length=1)
    content = discord.ui.TextInput(
        label='Issue Content',
        required=True,
        style=discord.TextStyle.long,
        min_length=1,
        max_length=2000
    )

    def __init__(self):
        super().__init__()
        self.repo_owner = None
        self.repo_name = None

    def set_repo(self, repo_owner: str, repo_name: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name

    async def on_submit(self, interaction: discord.Interaction):
        # GitHub API request to create an issue
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        data = {
            "title": self.name.value,  # Use the `name` input field for the issue title
            "body": self.content.value  # Use the `content` input field for the issue body
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 201:  # Issue created successfully
            issue_url = response.json().get("html_url", "Unknown URL")
            await interaction.response.send_message(
                f"Issue created successfully! [View Issue]({issue_url})",
                ephemeral=True
            )
        elif response.status_code == 404:
            await interaction.response.send_message(
                "Failed to create issue: Repository not found.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Failed to create issue: {response.status_code} {response.text}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"You fucked up! {error}", ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)


class Git(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    # Function to fetch the latest commit from a GitHub repository
    @staticmethod
    def get_latest_commit(repo_owner, repo_name):
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            commit_data = response.json()[0]  # Get the latest commit
            commit_message = commit_data['commit']['message']
            author = commit_data['commit']['author']['name']
            commit_url = commit_data['html_url']
            return f"Latest Commit: \n**Message**: {commit_message}\n**Author**: {author}\n[View Commit]({commit_url})"
        elif response.status_code == 404:
            return "Repository not found. Please check the owner and repository name."
        else:
            return f"Failed to fetch commit data. HTTP Status: {response.status_code}"

    @staticmethod
    # Function to search repositories on GitHub
    def search_repositories(query, sort="stars", order="desc"):
        url = "https://api.github.com/search/repositories"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        params = {"q": query, "sort": sort, "order": order}

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            repo_data = response.json()
            if repo_data["total_count"] == 0:
                return "No repositories found matching the search query."

            # Show the top 3 results
            result = "**Top Repositories:**\n"
            for repo in repo_data["items"][:3]:
                repo_name = repo["full_name"]
                description = repo["description"] or "No description provided."
                stars = repo["stargazers_count"]
                repo_url = repo["html_url"]
                result += f"🔹 **[{repo_name}]({repo_url})**\n⭐ {stars} stars\n📖 {description}\n\n"

            return result
        else:
            return f"Failed to search repositories. HTTP Status: {response.status_code}"

    @staticmethod
    def get_open_issues(repo_owner, repo_name):
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            issues = response.json()
            if not issues:
                return "No open issues found in this repository."

            # Format the top 5 issues
            result = "**Open Issues:**\n"
            for issue in issues[:5]:  # Limit to the top 5 issues
                issue_title = issue["title"]
                issue_number = issue["number"]
                issue_url = issue["html_url"]
                result += f"🔹 **#{issue_number}: [{issue_title}]({issue_url})**\n"

            return result
        elif response.status_code == 404:
            return "Repository not found. Please check the owner and repository name."
        else:
            return f"Failed to fetch issues. HTTP Status: {response.status_code}"

    # Define the hybrid command to get the latest commit
    @commands.hybrid_command(name="latest_commit", description="Get the latest commit from a GitHub repository")
    @app_commands.describe(owner="Owner of the repository", repo="Name of the repository")
    async def latest_commit(self, ctx: commands.Context, owner: str, repo: str):
        await ctx.defer()  # Defers the response to allow time for processing

        commit_info = self.get_latest_commit(owner, repo)  # call static func
        await ctx.send(commit_info)

    @app_commands.command(name="create_issue", description="Create a new issue")
    @app_commands.describe(owner="Owner of the repository", repo="Name of the repository")
    async def create_issue(self, interaction: discord.Interaction, owner: str, repo: str):
        if not GITHUB_TOKEN:
            await interaction.response.send_message(
                "GitHub token is not configured. Cannot create issues.",
                ephemeral=True
            )
            return

        modal = CreateIssue()
        modal.set_repo(repo_owner=owner, repo_name=repo)
        await interaction.response.send_modal(modal)

    # defione the slash command to search for repos
    @app_commands.command(name="repo_search", description="Search repositories")
    @app_commands.describe(query="Search query (e.g., 'discord bot')", sort="Sort by (stars, forks, etc.)",
                           order="Order (asc, desc)")
    async def search_repos(self, interaction: discord.Interaction, query: str, sort: str = "stars",
                           order: str = "desc"):
        await interaction.response.defer()  # Defers the response to allow time for processing
        search_result = self.search_repositories(query, sort, order)
        await interaction.followup.send(search_result)

    # Define the slash command to list open issues
    @app_commands.command(name="list_issues", description="List open issues in a GitHub repository")
    @app_commands.describe(owner="Owner of the repository", repo="Name of the repository")
    async def list_issues(self, interaction: discord.Interaction, owner: str, repo: str):
        await interaction.response.defer()  # Defer response for processing time

        issues = self.get_open_issues(owner, repo)
        await interaction.followup.send(issues)


async def setup(bot):
    await bot.add_cog(Git(bot))
