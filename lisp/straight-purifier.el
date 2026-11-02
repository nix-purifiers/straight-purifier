;;; straight-purifier.el --- Locked Straight packages -*- lexical-binding: t -*-
;; Version: 0.1.0
;; Package-Requires: ((emacs "29.1"))
;; SPDX-License-Identifier: MIT
(require 'cl-lib)
(defvar straight-purifier--environment nil)
(defvar straight-purifier--nix-delivered nil)
(defvar straight-purifier--recipes nil)
(defun straight-purifier--deny (&rest _)
  (error "Straight packages are locked; run straight-purifier lock/update and prefetch"))
(defun straight-purifier--check-recipe (recipe)
  (unless (equal recipe (cdr (assoc (plist-get recipe :package) straight-purifier--recipes)))
    (straight-purifier--deny)))
(defun straight-purifier--register-locked (&rest _)
  (dolist (recipe straight-purifier--recipes)
    (straight-register-package (cons (intern (car recipe)) (cdr recipe)))))
(defun straight-purifier--bootstrap-path (path)
  (let ((root (getenv "STRAIGHT_PURIFIER_ROOT")))
    (and root (stringp path)
         (equal (expand-file-name path)
                (expand-file-name "straight/repos/straight.el/bootstrap.el" root)))))
(defun straight-purifier--file-exists (original path)
  (if (straight-purifier--bootstrap-path path) t (funcall original path)))
(defun straight-purifier--load (original file &rest arguments)
  (apply original (if (straight-purifier--bootstrap-path file)
                      (expand-file-name "straight/repos/straight.el/bootstrap.el" straight-purifier--environment)
                    file) arguments))
(defun straight-purifier--activate (environment)
  (unless (equal straight-purifier--environment environment)
    (setq straight-purifier--environment environment
          straight-base-dir (file-name-as-directory environment)
          straight-safe-mode t
          straight-disable-native-compile t
          straight-check-for-modifications nil
          straight-initial-recipe-repositories nil)
    (load (expand-file-name "straight/repos/straight.el/bootstrap.el" environment) nil t)
    (setq straight-purifier--recipes
          (with-temp-buffer
            (insert-file-contents (expand-file-name "recipes.el" environment))
            (let ((read-eval nil))
              (mapcar (lambda (form) (cons (symbol-name (car form)) (cdr form))) (read (current-buffer))))))
    (advice-add 'straight--register-recipe :before #'straight-purifier--check-recipe)
    (straight-purifier--register-locked)
    (advice-add 'straight--reset-caches :after #'straight-purifier--register-locked)
    (dolist (function '(straight-vc-clone straight-vc-fetch-from-remote
                        straight-vc-pull-from-remote straight-thaw-versions
                        straight-freeze-versions straight-rebuild-package straight-rebuild-all))
      (advice-add function :override #'straight-purifier--deny))
    (advice-add 'file-exists-p :around #'straight-purifier--file-exists)
    (advice-add 'load :around #'straight-purifier--load)))
;;;###autoload
(defun straight-purifier-activate ()
  "Activate the locked environment for this Emacs configuration."
  (interactive)
  (unless (getenv "STRAIGHT_PURIFIER_LOCKING")
    (unless straight-purifier--nix-delivered
      (display-warning 'straight-purifier
                       "straight-purifier was resolved impurely; use the Emacs wrapper for pure resolution of the integration." :warning))
    (unless straight-purifier--environment
      (if (not (file-exists-p (or (getenv "STRAIGHT_PURIFIER_LOCKFILE")
                                  (expand-file-name "straight-purifier.lock.json" user-emacs-directory))))
          (display-warning 'straight-purifier "No lockfile; using ordinary impure Straight." :warning)
        (require 'json)
        (with-temp-buffer
          (let ((status (call-process "straight-purifier" nil t nil
                                      "--project" user-emacs-directory "prefetch" "--json")))
            (unless (eq status 0) (error "straight-purifier prefetch failed: %s" (buffer-string)))
            (goto-char (point-min))
            (load (expand-file-name "site-lisp/site-start.el"
                                    (alist-get 'environment (json-parse-buffer :object-type 'alist))) nil t)))))))
(provide 'straight-purifier)
;;; straight-purifier.el ends here
