// Runs the browser's own update-signature code (browser/modules/OrbitSignature.sys.mjs)
// under Node, for tests/test_build.py:
//
//   node tests/verify_signature.mjs hash <file> [piece size]   the file's BLAKE2b-512, in hex
//   node tests/verify_signature.mjs verify <file> <signature file> <public key>
//                                                               the trusted comment's fields, as JSON
//
// A failed check prints the browser's message and exits 1.

import { readFileSync } from "node:fs";
import { Blake2b, verifyUpdateSignature } from "../browser/modules/OrbitSignature.sys.mjs";

function digest(path, pieceSize = 65536) {
  const bytes = new Uint8Array(readFileSync(path));
  const hash = new Blake2b();
  for (let i = 0; i < bytes.length; i += pieceSize) {
    hash.update(bytes.subarray(i, i + pieceSize));
  }
  return hash.digest();
}

const [command, path, ...rest] = process.argv.slice(2);
try {
  if (command === "hash") {
    console.log(Buffer.from(digest(path, Number(rest[0]) || 65536)).toString("hex"));
  } else if (command === "verify") {
    const [signature, publicKey] = rest;
    console.log(JSON.stringify(await verifyUpdateSignature(digest(path), readFileSync(signature, "utf8"), publicKey)));
  } else {
    throw new Error(`unknown command ${command}`);
  }
} catch (error) {
  console.log(error.message);
  process.exit(1);
}
