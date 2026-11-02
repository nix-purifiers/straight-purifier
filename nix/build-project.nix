# SPDX-License-Identifier: MIT
{
  lib,
  runCommand,
  writeText,
  fetchurl,
  fetchgit,
  python3,
  git,
  emacs,
  gnutar,
  gzip,
  purifier,
}:
{
  src,
  lockFile ? src + "/straight-purifier.lock.json",
  configFile ? src + "/init.el",
  nativeLock ? src + "/straight/versions/default.el",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  testFile ? null,
  srcFilter ?
    path: type:
    !(builtins.elem (baseNameOf path) [
      "straight"
      ".git"
      ".straight-purifier"
      "result"
    ]),
}:
let
  source = lib.cleanSourceWith {
    inherit src;
    filter = srcFilter;
  };
  lock = purifier.checkLock (
    (import ./read-lock.nix { inherit lib; }) {
      inherit
        src
        lockFile
        configFile
        nativeLock
        ;
    }
  );
  environment =
    (import ./environment.nix {
      inherit
        lib
        runCommand
        writeText
        fetchurl
        fetchgit
        python3
        git
        emacs
        purifier
        ;
    })
      {
        inherit lock fetchers;
        extraNativeBuildInputs = nativeBuildInputs;
      };
  tests =
    runCommand "straight-project-tests"
      {
        nativeBuildInputs = [
          emacs
          git
        ];
      }
      ''
        export HOME="$TMPDIR/home"
        mkdir -p "$HOME"
        emacs --batch -Q --load ${environment}/site-lisp/site-start.el \
          ${
            if testFile != null then
              "--load ${lib.escapeShellArg "${testFile}"} --funcall ert-run-tests-batch-and-exit"
            else
              "--eval "
              + lib.escapeShellArg "(mapc #'straight-use-package '(${
                lib.concatStringsSep " " (map (p: p.name) lock.recipes)
              }))"
          }
        touch "$out"
      '';
  release =
    runCommand "emacs-config-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        test -e ${tests}
        mkdir -p "$out" "$TMPDIR/release"
        cp -r ${source}/. "$TMPDIR/release/"
        chmod -R u+w "$TMPDIR/release"
        cp ${configFile} "$TMPDIR/release/${baseNameOf configFile}"
        mkdir -p "$TMPDIR/release/straight/versions"
        cp ${nativeLock} "$TMPDIR/release/straight/versions/default.el"
        cp ${lockFile} "$TMPDIR/release/straight-purifier.lock.json"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner \
          -C "$TMPDIR/release" -cf - . | gzip -n > "$out/config.tar.gz"
      '';
in
builtins.seq lock {
  packages.environment = environment;
  inherit tests release;
  fetches = lock.entries;
}
