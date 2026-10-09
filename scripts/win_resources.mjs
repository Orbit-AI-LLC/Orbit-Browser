// Orbit Browser's icons and details in Firefox's Windows executables.
//
//   node scripts/win_resources.mjs "work/win64/Orbit Browser" 0.1.0-build.12
//
// scripts/build.py runs this. firefox.exe carries Firefox's icons as groups:
// 1 and 32512 the app, 2 the HTML document, 5 private browsing, 6 the PDF
// document, 3 and 4 the jump list's new window and tab, and 1100-1107 the
// alternative icons Firefox lets people pick (Orbit Browser turns the picker
// off). Every group becomes the matching Orbit Browser icon, and the version
// details name Orbit Browser and its version (the file version stays
// Firefox's). Editing an executable drops Mozilla's Authenticode signature
// from it.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import * as PELibrary from "pe-library";
import * as ResEdit from "resedit";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const [appDir, version] = process.argv.slice(2);
if (!appDir || !version) {
  console.error("usage: node scripts/win_resources.mjs <app folder> <version>");
  process.exit(2);
}

function icon(name) {
  return ResEdit.Data.IconFile.from(readFileSync(join(root, "branding", "windows", name)));
}

const app = icon("firefox.ico");
const privateBrowsing = icon("private_browsing.ico");
const documentIcon = icon("document.ico");
const ICON_FOR_GROUP = { 2: documentIcon, 5: privateBrowsing, 6: documentIcon };

function edit(file, { description, iconFor }) {
  const path = join(appDir, file);
  const exe = PELibrary.NtExecutable.from(readFileSync(path), { ignoreCert: true });
  const res = PELibrary.NtExecutableResource.from(exe);

  for (const group of ResEdit.Resource.IconGroupEntry.fromEntries(res.entries)) {
    const replacement = iconFor(group.id);
    ResEdit.Resource.IconGroupEntry.replaceIconsForResource(
      res.entries,
      group.id,
      group.lang,
      replacement.icons.map((item) => item.data),
    );
  }

  const [info] = ResEdit.Resource.VersionInfo.fromEntries(res.entries);
  for (const language of info.getAllLanguagesForStringValues()) {
    info.setStringValues(language, {
      CompanyName: "Orbit LLC",
      FileDescription: description,
      ProductName: "Orbit Browser",
      InternalName: "Orbit Browser",
      LegalCopyright: "Orbit Browser is built on Firefox: © Firefox and Mozilla Developers, available under the MPL 2 license.",
      LegalTrademarks: "Firefox is a trademark of the Mozilla Foundation.",
      ProductVersion: version,
    });
  }
  info.outputToResourceEntries(res.entries);

  res.outputResource(exe);
  writeFileSync(path, Buffer.from(exe.generate()));
  console.log(`${file}: icons and details are Orbit Browser's`);
}

edit("firefox.exe", { description: "Orbit Browser", iconFor: (id) => ICON_FOR_GROUP[id] ?? app });
edit("private_browsing.exe", { description: "Orbit Browser private window", iconFor: () => privateBrowsing });
