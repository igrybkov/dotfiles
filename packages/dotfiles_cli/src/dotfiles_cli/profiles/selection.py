"""Profile selection parsing and resolution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProfileSelection:
    """Represents a parsed profile selection.

    Supports selection syntax:
    - 'common,mycompany' -> explicit profiles
    - '-mycompany' -> all except mycompany (exclusion)
    - 'all' -> all profiles
    - 'all,-mycompany' -> all except mycompany
    - (empty) -> common only
    """

    explicit_profiles: list[str] = field(default_factory=list)
    excluded_profiles: list[str] = field(default_factory=list)
    include_all: bool = False

    def resolve(self, available: list[str]) -> list[str]:
        """Resolve to final list of profile names.

        Args:
            available: List of all available profile names

        Returns:
            Sorted list of resolved profile names
        """
        if self.include_all:
            # Start with all available profiles
            result = set(available)
        elif self.explicit_profiles:
            # Only use explicitly listed profiles
            result = set(self.explicit_profiles)
        else:
            # Default: common only
            result = {"common"}

        # Apply exclusions
        result -= set(self.excluded_profiles)

        # Filter to only available profiles (ignore invalid names)
        result &= set(available)

        return sorted(result)


def parse_profile_selection(selection: str | None) -> ProfileSelection:
    """Parse profile selection syntax.

    Supports:
    - 'common,work' -> explicit profiles
    - '-mycompany' -> all except mycompany
    - 'all' -> all profiles
    - 'all,-mycompany' -> all except mycompany
    - (empty/None) -> common only

    Args:
        selection: Comma-separated profile selection string

    Returns:
        ProfileSelection object
    """
    if not selection or selection.strip() == "":
        return ProfileSelection()

    parts = [p.strip() for p in selection.split(",")]

    explicit: list[str] = []
    excluded: list[str] = []
    include_all = False

    for part in parts:
        if not part:
            continue
        if part.lower() == "all":
            include_all = True
        elif part.startswith("-"):
            profile_name = part[1:]
            if profile_name:
                excluded.append(profile_name)
        else:
            explicit.append(part)

    # If only exclusions provided (e.g., "-mycompany"), implies "all,-mycompany"
    if excluded and not explicit and not include_all:
        include_all = True

    return ProfileSelection(
        explicit_profiles=explicit,
        excluded_profiles=excluded,
        include_all=include_all,
    )
