{
  description = "StatShed CLI - command-line interface for the StatShed status dashboard";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;
        pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);

        statshed-cli = python.pkgs.buildPythonApplication {
          pname = "statshed-cli";
          version = pyproject.project.version;
          pyproject = true;
          src = ./.;

          build-system = [ python.pkgs.hatchling ];

          dependencies = with python.pkgs; [
            click
            requests
            pyyaml
          ];

          optional-dependencies = {
            rich = [ python.pkgs.rich ];
          };

          nativeCheckInputs = with python.pkgs; [
            pytestCheckHook
            responses
            rich
          ];

          # AIDEV-NOTE: integration tests need a live backend (gated by
          # STATSHED_INTEGRATION); skip the file entirely in the sandbox.
          disabledTestPaths = [ "tests/test_integration.py" ];

          postInstall = ''
            install -Dm0644 docs/statshed.1 $out/share/man/man1/statshed.1
          '';

          pythonImportsCheck = [ "statshed_cli" ];

          meta = with pkgs.lib; {
            description = "Command-line interface for the StatShed status dashboard";
            homepage = "https://github.com/statshed/statshed-pycli";
            license = licenses.cc0;
            mainProgram = "statshed";
            platforms = platforms.all;
          };
        };
      in
      {
        packages.default = statshed-cli;
        packages.statshed-cli = statshed-cli;

        apps.default = {
          type = "app";
          program = "${statshed-cli}/bin/statshed";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.uv
            python
            pkgs.ruff
            python.pkgs.mypy
          ];
        };
      });
}
