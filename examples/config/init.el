;;; init.el --- Example Straight configuration -*- lexical-binding: t -*-
(setq straight-check-for-modifications nil)
(load (expand-file-name "straight/repos/straight.el/bootstrap.el"
                        (or (bound-and-true-p straight-base-dir) user-emacs-directory)) nil t)
(straight-use-package '(s :type git :host github :repo "magnars/s.el"))
(require 's)
