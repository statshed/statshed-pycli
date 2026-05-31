# AIDEV-NOTE: Native RPM spec for statshed-cli, built in CI on Fedora and
# Rocky/EL9 (EPEL) via pyproject-rpm-macros. The Version below MUST match
# pyproject.toml and debian/changelog; the release workflow's check-version job
# fails the build on drift. Source0 is the sdist produced by `uv build`, which
# is named with the normalized module name (underscores: statshed_cli-X.Y.Z).

%global pypi_name   statshed-cli
%global import_name statshed_cli

Name:           %{pypi_name}
Version:        1.0.2
Release:        1%{?dist}
Summary:        Command-line interface for the StatShed status dashboard

License:        CC0-1.0
URL:            https://github.com/statshed/statshed-pycli
Source0:        %{import_name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
# For %%check
BuildRequires:  python3-pytest
BuildRequires:  python3-responses

Requires:       python3-click
Requires:       python3-requests
Requires:       python3-pyyaml
Recommends:     python3-rich

%description
StatShed CLI provides commands for interacting with the StatShed status
dashboard from the command line: submitting job status, checking health,
listing groups and jobs, managing global and per-group configuration,
uploading logs, and generating shell completion scripts.

%prep
%autosetup -n %{import_name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{import_name}
install -Dpm0644 docs/statshed.1 %{buildroot}%{_mandir}/man1/statshed.1

%check
%pytest

%files -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/statshed
%{_mandir}/man1/statshed.1*

%changelog
* Sat May 31 2026 Sean <jafo00+oss@gmail.com> - 1.0.2-1
- Initial RPM packaging.
