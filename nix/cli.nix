# SPDX-License-Identifier: MIT
{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  emacs,
  gh,
  git,
  nix-prefetch-git,
  cacert,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "straight-purifier";
  version = "0.1.0";
  src = ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/straight-purifier" "$out/share/emacs/site-lisp"
    cp -r straight_purifier nix lisp "$out/lib/straight-purifier/"
    cp lisp/straight-purifier.el "$out/share/emacs/site-lisp/"
    install -m755 bin/straight-purifier "$out/bin/straight-purifier"
    substituteInPlace "$out/lib/straight-purifier/nix/realize.nix" \
      --replace-fail '@nixpkgs@' '${nixpkgsSrc}' \
      --replace-fail '@purifier@' '${purifierSrc}' \
      --replace-fail '@runtime@' "$out"
    wrapProgram "$out/bin/straight-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          emacs
          gh
          git
          nix-prefetch-git
        ]
      } \
      --prefix PYTHONPATH : "$out/lib/straight-purifier" \
      --set STRAIGHT_PURIFIER_EMACS_VERSION ${emacs.version} \
      --set STRAIGHT_PURIFIER_EMACS ${emacs}/bin/emacs \
      --set STRAIGHT_PURIFIER_RESOLVER "$out/lib/straight-purifier/lisp/resolve.el" \
      --set STRAIGHT_PURIFIER_REALIZE "$out/lib/straight-purifier/nix/realize.nix" \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt
    makeWrapper "$out/bin/straight-purifier" "$out/bin/emacs" --add-flags "native --"
  '';
  meta = {
    description = "Locked, Nix-resolved Emacs packages";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
    mainProgram = "straight-purifier";
    homepage = "https://nix-purifiers.github.io/";
  };
}
