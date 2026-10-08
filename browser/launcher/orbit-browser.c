/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/*
 * The Mac app's executable (CFBundleExecutable). It runs Firefox's engine,
 * Contents/MacOS/firefox, with Orbit Browser's own application.ini
 * (Contents/Resources/browser/application.ini, written by scripts/build.py),
 * the way Firefox's -app flag does: the engine is Firefox's, but its data
 * lives in ~/Library/Application Support/Orbit Browser, not in Firefox's
 * folder (which macOS keeps for Firefox alone).
 *
 * The file goes in XUL_APP_FILE rather than on the command line, so the
 * engine keeps it when it restarts itself. exec keeps this process, so to
 * macOS it is still the app it launched.
 */

#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char* argv[]) {
  char here[PATH_MAX];
  uint32_t size = sizeof(here);
  char resolved[PATH_MAX];
  if (_NSGetExecutablePath(here, &size) != 0 || !realpath(here, resolved)) {
    fprintf(stderr, "Orbit Browser: can't find its own executable.\n");
    return 1;
  }
  char* slash = strrchr(resolved, '/');
  if (!slash) {
    return 1;
  }
  *slash = '\0';  // resolved is now Contents/MacOS

  char engine[PATH_MAX];
  char app_ini[PATH_MAX];
  if (snprintf(engine, sizeof(engine), "%s/firefox", resolved) >= (int)sizeof(engine) ||
      snprintf(app_ini, sizeof(app_ini), "%s/../Resources/browser/application.ini", resolved) >=
          (int)sizeof(app_ini)) {
    return 1;
  }
  char ini[PATH_MAX];
  if (!realpath(app_ini, ini)) {
    fprintf(stderr, "Orbit Browser: %s is missing.\n", app_ini);
    return 1;
  }
  setenv("XUL_APP_FILE", ini, 1);

  argv[0] = engine;
  execv(engine, argv);
  perror("Orbit Browser: can't start its engine");
  return 1;
}
