# SPDX-License-Identifier: MIT
{
  project,
  configFile,
  lockFile,
  nativeLock,
  target,
}:
let
  pkgs = import (builtins.toPath "@nixpkgs@") { };
  purifier = import (builtins.toPath "@purifier@/nix/lib") { inherit (pkgs) lib; };
  args = {
    src = /. + project;
    configFile = /. + configFile;
    lockFile = /. + lockFile;
    nativeLock = /. + nativeLock;
  };
in
if target == "environment" then
  (pkgs.callPackage ../pkgs/build-straight-project/default.nix { inherit purifier; } args).packages.environment
else if target == "runtime" then
  pkgs.runCommand "straight-runtime" { } ''ln -s @runtime@ "$out"''
else if target == "release" then
  (pkgs.callPackage ../pkgs/build-straight-project/default.nix { inherit purifier; } args).release
else
  throw "straight-purifier: unknown realization target ${target}"
