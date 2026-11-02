# SPDX-License-Identifier: MIT
{ pkgs, self }:
let
  project = pkgs.straight-purifier.buildStraightProject {
    src = ../examples/config;
    testFile = ./integration.el;
  };
in
{
  cli = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
  environment = project.packages.environment;
  project = project.tests;
  release = project.release;
}
