from itertools import chain
from pprint import pprint

import click
from cache_to_disk import cache_to_disk
from ghapi.all import GhApi, paged


@cache_to_disk(1)
def load_teams_data_from_github(org):
    """
    returns a Tuple of

    - fully_empty_teams: A list of team slugs of teams that have no members, repos, projects or
      sub_teams.
    - members_but_nothing_else: A list of team slugs for teams that have members but nothing else.
    - team_to_members: A mapping of team slugs to a list of team member logins.
    """
    api = GhApi()

    # Get teams and their related artifacts.
    teams = []
    fully_empty_teams = []
    members_but_nothing_else = []
    team_to_members = {}
    teams = chain.from_iterable(paged(api.teams.list, org, per_page=100))

    for team in teams:
        # we ignore the fact that there could be multiple pages of responses because we don't need
        # a full list of teams, since we're just looking for the teams that don't have any of these
        # objects.
        has_repos = bool(api.teams.list_repos_in_org(org, team.slug))
        has_projects = bool(api.teams.list_projects_in_org(org, team.slug))
        has_child_teams = bool(api.teams.list_child_in_org(org, team.slug))

        # We get all the team members so we can review teams that still
        # have members.
        # We convert this to a list so that we can do boolean checks with
        # it later
        team_members = list(
            chain.from_iterable(paged(api.teams.list_members_in_org, org, team.slug))
        )

        team_to_members[team.slug] = [member.login for member in team_members]
        if not (has_repos or has_projects or has_child_teams):
            if team_members:
                members_but_nothing_else.append(team.slug)
            else:
                fully_empty_teams.append(team.slug)

    # Leaving this as a complex 3-tuple but if we're making more changes, it
    # probably makes sense to create a `Team` class with things like `members`
    # and `has_projects` as attributes and computed properties for things like
    # `members_but_nothing_else`.
    return (fully_empty_teams, members_but_nothing_else, team_to_members)


@click.option(
    "--org", default="openedx", help="The github org that you wish to cleanup."
)
@click.option(
    "--dry-run",
    "-n",
    default=False,
    is_flag=True,
    help="Show what changes would be made without making them.",
)
@click.option(
    "--refresh-cache",
    help="Refresh cache of github data before running.",
    default=False,
    is_flag=True,
)
@click.command()
def main(org, dry_run, refresh_cache):
    if refresh_cache:
        load_teams_data_from_github.cache_clear()

    deletion_count = 0
    api = GhApi()
    teams = []
    teams = chain.from_iterable(paged(api.teams.list, org, per_page=100))
    for team in teams:
        repos = api.teams.list_repos_in_org(org, team.slug)
        has_repos = bool(repos)
        # assumes pagination will not pose an issue; true for edx-ops but not for larger teams
        count_of_repos = len(repos)
        # uninteresting for edx-ops
        #has_projects = bool(api.teams.list_projects_in_org(org, team.slug))
        # don't need to keep pulling this; only one child team relationship I've already noted
        #has_child_teams = bool(api.teams.list_child_in_org(org, team.slug))
        # assumes pagination will not pose an issue; true for edx-ops but not for larger teams
        members = api.teams.list_members_in_org(org, team.slug)
        count_of_members = len(members)

        print(f'{team.slug}\t{team.privacy}\t{count_of_repos}\t{count_of_members}')

        if members:
            print(members[0])


if __name__ == "__main__":
    main()
