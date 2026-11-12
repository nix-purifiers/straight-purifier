# SPDX-License-Identifier: MIT
{ lib }:
{
  src,
  lockFile ? src + "/straight-purifier.lock.json",
  configFile ? src + "/init.el",
  nativeLock ? src + "/straight/versions/default.el",
}:
let
  problem = message: "straight-purifier: ${message}; run straight-purifier lock";
  exists = builtins.all builtins.pathExists [
    lockFile
    configFile
    nativeLock
  ];
  data =
    if exists then
      builtins.addErrorContext (problem "cannot parse companion lock") (
        builtins.fromJSON (builtins.readFile lockFile)
      )
    else
      { };
  nameRe = "[A-Za-z0-9][A-Za-z0-9_.+-]*";
  nameOK =
    x:
    builtins.isString x
    && builtins.match nameRe x != null
    && !(builtins.elem x [
      "."
      ".."
    ]);
  pieces =
    if exists then
      builtins.split ''\("(${nameRe})"[[:space:]]*\.[[:space:]]*"([0-9a-f]{40})"\)'' (
        builtins.readFile nativeLock
      )
    else
      [ ];
  pairs = builtins.filter builtins.isList pieces;
  pins = builtins.listToAttrs (
    map (pair: {
      name = builtins.head pair;
      value = builtins.elemAt pair 1;
    }) pairs
  );
  remainder = lib.concatStrings (builtins.filter builtins.isString pieces);
  ignored = [
    ".git"
    "straight"
    ".straight-purifier"
    "eln-cache"
    "auto-save-list"
    "__pycache__"
    "result"
  ];
  walk =
    prefix: directory:
    lib.concatMap (
      name:
      let
        kind = (builtins.readDir directory).${name};
        relative = prefix + name;
        path = directory + "/${name}";
      in
      if builtins.elem name ignored then
        [ ]
      else if kind == "directory" then
        walk "${relative}/" path
      else
        lib.optional (lib.hasSuffix ".el" name) {
          name = relative;
          value = builtins.hashFile "sha256" path;
        }
    ) (builtins.attrNames (builtins.readDir directory));
  inputs = builtins.listToAttrs (walk "" src);
  repositories = data.repositories or { };
  recipes = data.recipes or [ ];
  repoOK =
    name:
    let
      m = repositories.${name};
    in
    nameOK name
    && builtins.isAttrs m
    && builtins.isString (m.url or null)
    && builtins.match "(https?://|ssh://|git@|file://|/)[^[:space:]]+" m.url != null
    && (m.rev or null) == (pins.${name} or null)
    && builtins.isString (m.hash or null)
    && builtins.match "sha256-[A-Za-z0-9+/]{43}=" m.hash != null
    && builtins.isAttrs (m.commitObject or null)
    && builtins.isString (m.commitObject.object or null)
    && builtins.isList (m.commitObject.gitlinks or null);
  problems = map problem (
    if !exists then
      [ "missing configuration or locks" ]
    else if !builtins.isAttrs data || (data.version or null) != 1 then
      [ "unsupported companion format" ]
    else if
      (data.contentHash or null)
      != builtins.hashString "sha256" (builtins.toJSON (removeAttrs data [ "contentHash" ]))
    then
      [ "contentHash mismatch" ]
    else if
      (data.nativeHash or null) != builtins.hashFile "sha256" nativeLock
      || (data.configHash or null) != builtins.hashFile "sha256" configFile
      || (data.inputs or null) != inputs
    then
      [ "configuration or native lock changed" ]
    else if
      builtins.match ''[[:space:]]*\([[:space:]]*\)[[:space:]]*:epsilon[[:space:]]*'' remainder == null
      || builtins.length pairs != builtins.length (builtins.attrNames pins)
    then
      [ "unsupported native lock format" ]
    else if
      !builtins.isAttrs repositories
      || builtins.attrNames repositories != builtins.attrNames pins
      || !(repositories ? "straight.el")
    then
      [ "missing native repository metadata" ]
    else if !builtins.all repoOK (builtins.attrNames repositories) then
      [ "invalid native repository metadata" ]
    else if
      !builtins.isList recipes
      || !builtins.all (
        p: builtins.isAttrs p && nameOK (p.name or null) && builtins.isString (p.form or null)
      ) recipes
    then
      [ "invalid native recipes" ]
    else if builtins.length (lib.unique (map (p: p.name) recipes)) != builtins.length recipes then
      [ "duplicate recipe" ]
    else if
      !builtins.isString (data.emacsVersion or null) || !builtins.isList (data.recipeRepositories or null)
    then
      [ "missing native environment metadata" ]
    else
      [ ]
  );
  usable = problems == [ ];
in
{
  purifier = "straight-purifier";
  inherit problems;
  outputs.environment = { };
  entries =
    if !usable then
      [ ]
    else
      map (name: {
        path = name;
        inherit (repositories.${name}) hash;
        git = {
          inherit (repositories.${name}) url rev commitObject;
          submodules = true;
          leaveDotGit = true;
        };
      }) (builtins.attrNames repositories);
  recipes = if usable then recipes else [ ];
  recipeRepositories = data.recipeRepositories or [ ];
  emacsVersion = data.emacsVersion or "";
}
