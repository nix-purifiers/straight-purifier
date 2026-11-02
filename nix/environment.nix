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
  purifier,
}:
{
  lock,
  fetchers ? { },
  extraNativeBuildInputs ? [ ],
}:
let
  checked = purifier.checkLock lock;
  sources = purifier.tree (
    {
      name = "straight-repositories";
      entries = checked.entries;
      inherit
        runCommand
        fetchurl
        fetchgit
        python3
        ;
    }
    // fetchers
  );
  recipesFile = writeText "straight-recipes.el" "(${
    lib.concatMapStringsSep "\n" (p: p.form) checked.recipes
  })\n";
  installScript = writeText "straight-install.el" ''
    ;;; -*- lexical-binding: t -*-
    (setq user-emacs-directory (concat (getenv "out") "/")
          straight-base-dir user-emacs-directory
          straight-disable-native-compile t
          straight-check-for-modifications nil
          straight-initial-recipe-repositories nil)
    (load (expand-file-name "straight/repos/straight.el/bootstrap.el" user-emacs-directory) nil t)
    (let ((recipes (with-temp-buffer (insert-file-contents "${recipesFile}") (read (current-buffer)))))
      (mapc #'straight-register-package recipes)
      (setq straight-recipe-repositories '(${lib.concatStringsSep " " checked.recipeRepositories}))
      (mapc (lambda (recipe) (straight-use-package (car recipe))) recipes))
    ;; Native modification timestamps are irrelevant in an immutable tree.
    (maphash (lambda (_ record) (setcar record "1970-01-01 00:00:01"))
             straight--build-cache)
    (straight--transaction-finalize)
  '';
  siteStart = writeText "straight-site-start.el" ''
    ;;; site-start.el --- Locked Straight packages -*- lexical-binding: t -*-
    (add-to-list 'exec-path "${git}/bin")
    (load "${../lisp/straight-purifier.el}" nil t)
    (setq straight-purifier--nix-delivered t)
    (straight-purifier--activate "@environment@")
  '';

in
assert
  checked.emacsVersion == emacs.version
  || throw "straight-purifier: Emacs version differs from the lock; override the scope's emacs or update the lock";
runCommand "purified-straight-environment"
  {
    nativeBuildInputs = [
      emacs
      git
    ]
    ++ extraNativeBuildInputs;
  }
  ''
      export HOME="$TMPDIR/home"
      mkdir -p "$HOME" "$out/straight/repos" "$out/site-lisp"
      for repository in ${sources}/*; do
      name="$(basename "$repository")"
      mkdir -p "$out/straight/repos/$name"
      cp -r "$repository/." "$out/straight/repos/$name/"
    done
      chmod -R u+w "$out/straight/repos"
      cp ${recipesFile} "$out/recipes.el"
      emacs --batch -Q --load ${installScript}
      substitute ${siteStart} "$out/site-lisp/site-start.el" \
        --replace-fail '@environment@' "$out"
  ''
