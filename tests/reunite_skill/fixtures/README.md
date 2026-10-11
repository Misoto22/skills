# leveldb-sidebar

A small LevelDB database written by a real LevelDB implementation, so the reunite
skill's dependency-free reader and writer are tested against bytes they did not produce.
It is shaped like the desktop app's Chromium Local Storage: keys carry the
`_https://claude.ai\x00\x01` origin prefix, and `dframe-store` holds a Latin-1 sidebar
layout for two synthetic accounts — every UUID is made up and no real data is in it.

## Provenance

- Generator: Node `classic-level` 3.0.0 (bundled LevelDB 1.20 with Snappy), Node 26.7.0,
  run once in a scratch directory outside this repository on 2026-10-11. Node is not a
  dependency of this repository.
- The script below writes 40 filler keys, `VERSION`, a `META:` key, a put–delete–put
  sequence on `dframe-store`, and one deletion, then compacts the whole key range so
  those land in `000005.ldb` with Snappy-compressed blocks. Two later writes stay only
  in the write-ahead log `000004.log`.
- `LOG` (LevelDB's text info log) was not kept; LevelDB recreates it on open.

| file | sha256 |
|---|---|
| `000004.log` | `3d637d620af1f2951190ba23eaeb9fa37686c67c8ff0c5d2a0e234255e4496fc` |
| `000005.ldb` | `fad92fb6896ff2311acc79d2b7c97fabf5b6415d2db31046eee95f876e757bfc` |
| `CURRENT` | `1005a525006f148c86efcbfb36c6eac091b311532448010f70f7de9a68007167` |
| `LOCK` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `MANIFEST-000002` | `d13f3e97027a043c4893eecf47231f597f06e156a8edc9f30e3164dfcc91a4e7` |

To regenerate, run `npm install classic-level@3.0.0` in an empty scratch directory, save
the script there as `make-fixture.js`, run `node make-fixture.js out`, and copy every file
from `out/` except `LOG` over this directory. The sequence numbers and table layout the
tests assert follow from this exact script.

```js
const { ClassicLevel } = require("classic-level");

const ORIGIN = "_https://claude.ai\x00\x01";
const A = "aaaaaaaa-0000-4000-8000-00000000000a";
const B = "bbbbbbbb-0000-4000-8000-00000000000b";
const ORG_A = "0a0a0a0a-0000-4000-8000-0000000000a0";
const ORG_B = "0b0b0b0b-0000-4000-8000-0000000000b0";

function builtins() {
  const show = { metadata: true, emptyGroups: false };
  return [
    { id: "pinned", kind: "pinned", name: "", order: 0, sortBy: "manual", ascending: false, show, collapsed: false, shown: true },
    { id: "routines", kind: "routines", name: "", order: 1, sortBy: "recency", ascending: false, show, collapsed: false, shown: true },
    { id: "sessions", kind: "sessions", name: "", order: 2, sortBy: "recency", ascending: false, show, collapsed: false, shown: true },
  ];
}

function manual(id, name, order, members) {
  return {
    id, kind: "manual", name, order, sortBy: "recency", ascending: false,
    show: { metadata: true, emptyGroups: false }, collapsed: order % 2 === 0, shown: true, members,
  };
}

const store = {
  state: {
    collapsed: false,
    sidebarWidth: 253,
    pinnedOrder: ["code:local_s1"],
    groupByByMode: { code: "custom" },
    sortByByMode: { code: "recency" },
    codeSidebarByScope: {
      [`${A}/${ORG_A}`]: {
        sections: [
          ...builtins().slice(0, 2),
          manual("cg-alpha", "Alpha", 2, ["code:local_s1", "code:local_s2", "code:local_gone"]),
          manual("cg-beta", "Beta", 3, ["code:local_s3"]),
          { ...builtins()[2], order: 4 },
        ],
        migratedFrom: 1,
        prefsSeeded: true,
      },
      [`${B}/${ORG_B}`]: { sections: builtins(), migratedFrom: 1, prefsSeeded: true },
    },
    customGroupsByScope: {
      [`${A}/${ORG_A}`]: { groups: [{ id: "cg-alpha", name: "Alpha" }, { id: "cg-beta", name: "Beta" }] },
    },
    sidebarRowCountsByScope: { [`${A}/${ORG_A}`]: { "code.recents": 3 }, [`${B}/${ORG_B}`]: { "code.recents": 1 } },
  },
  version: 0,
};

async function main() {
  const db = new ClassicLevel(process.argv[2], { keyEncoding: "buffer", valueEncoding: "buffer" });
  await db.open();
  await db.put(Buffer.from("VERSION"), Buffer.from("1"));
  await db.put(Buffer.from("META:https://claude.ai"), Buffer.from([0x08, 0x01]));
  for (let i = 0; i < 40; i++) {
    const key = Buffer.from(`${ORIGIN}filler-${String(i).padStart(3, "0")}`, "latin1");
    await db.put(key, Buffer.concat([Buffer.from([1]), Buffer.from(`{"n":${i},"pad":"${"x".repeat(200)}"}`, "latin1")]));
  }
  const dframe = Buffer.from(`${ORIGIN}dframe-store`, "latin1");
  await db.put(dframe, Buffer.from("\x01{\"state\":{},\"version\":0}", "latin1"));
  await db.del(dframe);
  await db.put(dframe, Buffer.concat([Buffer.from([1]), Buffer.from(JSON.stringify(store), "latin1")]));
  await db.del(Buffer.from(`${ORIGIN}filler-039`, "latin1"));
  await db.compactRange(Buffer.from([0]), Buffer.from([0xff, 0xff]));
  await db.put(Buffer.from(`${ORIGIN}filler-000`, "latin1"), Buffer.from("\x01{\"n\":0,\"rewritten\":true}", "latin1"));
  await db.put(Buffer.from(`${ORIGIN}after-compaction`, "latin1"), Buffer.from("\x01log-only", "latin1"));
  await db.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
```
