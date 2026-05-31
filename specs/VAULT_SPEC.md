# VAULT Specification

Version 1.0 — 2026-03-25

Not a filesystem with database features. A fractal database with a filesystem interface.

---

## 1. Tier Semantics

VAULT classifies every entry into one of three tiers that determine security posture, storage topology, and access scope.

| Tier | C define | C value | Rust enum | CFA topology | Semantics |
|---|---|---|---|---|---|
| Sovereign | `VAULT_TIER_SOVEREIGN` | 0 | `Tier::Sovereign` | `TopologyConfig::sovereign()` | User data. Encrypted at rest. TPM-sealed seed. Never leaves the device. |
| Internal | `VAULT_TIER_INTERNAL` | 1 | `Tier::Internal` | `TopologyConfig::standard()` | App/process data. Scoped to the owning process or service. |
| Reference | `VAULT_TIER_REFERENCE` | 2 | `Tier::Reference` | `TopologyConfig::compact()` | Shared/public data. Read-optimized. Compact fractal addressing. |

**C implementation:** Tier is stored as a `uint32_t` field in `struct vault_inode`. The kernel enforces tier via `owner_pid` (Internal tier) and future encryption hooks (Sovereign tier).

**Rust implementation:** Each tier gets its own independent `CfaStore` instance, created during `Vault::format()`. The Sovereign tier's store is initialized with `CfaStore::init_with_tpm()` when `use_tpm` is true. Tier isolation is structural -- different stores, different CFA topologies, different fractal address spaces.

---

## 2. Entry Types

| Type | C define | C value | Rust enum | Wire schema value |
|---|---|---|---|---|
| Free (unused) | `VAULT_TYPE_FREE` | 0 | -- | -- |
| File | `VAULT_TYPE_FILE` | 1 | `EntryType::File` | `"file"` |
| Directory | `VAULT_TYPE_DIR` | 2 | `EntryType::Directory` | `"directory"` |
| Link | `VAULT_TYPE_LINK` | 3 | -- | `"link"` |
| Signal | `VAULT_TYPE_SIGNAL` | 4 | `EntryType::Signal` | `"signal"` |

**Notes:**
- The C implementation defines `VAULT_TYPE_LINK` (3) for symlink-like references. The Rust implementation does not yet implement Link as a variant of `EntryType`.
- The wire schema (`vault_entry.schema.json`) includes all four active types: `"file"`, `"directory"`, `"signal"`, `"link"`.
- `VAULT_TYPE_FREE` (0) is a C-only sentinel indicating an unused inode slot. It has no Rust or wire equivalent.
- Signal entries are live chain endpoints. The C header comments them as "live signal chain endpoint."

---

## 3. Version Chain

Every write creates a new version. No data is ever overwritten in place. The fractal database never forgets.

### C implementation

Versioning is implemented via inode copying. On write to a file that already has data:

1. A new inode is allocated via `alloc_inode()`.
2. The current inode's full contents are copied into the new slot (this becomes the "previous version").
3. The current inode's `prev_version` field is set to the new slot's inode number.
4. The current inode's `version` counter is incremented.

The previous version's data blocks are not freed -- they persist for temporal reads.

Relevant fields in `struct vault_inode`:

```c
uint32_t    prev_version;   /* Inode number of previous version (0 = none) */
uint32_t    version;        /* Version counter */
```

### Rust implementation

Versioning is implemented via an append-only `Vec<Version>` on each `VaultEntry`. On write:

1. A new `Version` record is created with a unique `data_id` (format: `"vault:{path}:v{id}"`).
2. The data is stored in the tier's `CfaStore` keyed by `data_id`.
3. The `Version` is pushed to the end of `entry.versions`.

All previous versions remain accessible because their `data_id` keys still exist in the CFA store.

Relevant struct:

```rust
pub struct Version {
    pub number: u32,        // Version number (0 = first)
    pub data_id: String,    // CFA data_id for this version's content
    pub size: usize,        // Size in bytes
    pub timestamp: u64,     // Unix epoch nanos
    pub is_append: bool,    // true if created by append (vs full write)
}
```

### Wire format

The wire `VaultEntry` carries a single version snapshot:

```json
{
  "version": <integer>,
  "prev_version": <integer | null>,
  "data_id": "<string>"
}
```

---

## 4. Temporal Reads

Both implementations use the same semantic convention: version 0 = current, version 1 = one version back, version 2 = two versions back, etc.

### C API

```c
// Read current version
int vault_read(const char *path, void *buf, uint32_t size);

// Read N versions back (0 = current, 1 = previous, ...)
int vault_read_version(const char *path, void *buf, uint32_t size, uint32_t version);
```

`vault_read_version` walks the `prev_version` inode chain N times:

```c
struct vault_inode *node = inode_ptr((uint32_t)ino);
for (uint32_t v = 0; v < version; v++) {
    if (!node || node->prev_version == 0)
        return -1;  /* Not enough history */
    node = inode_ptr(node->prev_version);
}
```

### Rust API

```rust
// Read current version (last in the versions vec)
pub fn read(&self, path: &str, tier: Tier) -> Result<Vec<u8>, VaultError>;

// Read N versions back (0 = current, 1 = previous, ...)
pub fn read_version(&self, path: &str, tier: Tier, version_back: u32) -> Result<Vec<u8>, VaultError>;
```

`read_version` indexes into the versions vec from the end:

```rust
let idx = (total - 1 - version_back) as usize;
let version = &entry.versions[idx];
```

### Wire operation

A temporal read is expressed as a query parameter or request field: `GET /vault/{path}?version={N}`. The service resolves this to the appropriate `data_id` and retrieves from the CFA store.

---

## 5. Delete Semantics

Both implementations agree: delete is soft. Data persists in temporal history. The fractal database never forgets.

### C implementation

`vault_delete()` sets the inode's `type` field to `VAULT_TYPE_FREE` and removes the directory entry from the parent. Data blocks are explicitly not freed:

```c
/* Mark inode as free (but data blocks persist for temporal history) */
node->type = VAULT_TYPE_FREE;
```

### Rust implementation

`Vault::delete()` sets the `deleted` flag to `true`. The entry remains in `VaultState::entries`. All version data remains in the CFA store:

```rust
entry.deleted = true;
```

Subsequent reads return `VaultError::Deleted`. `exists()` returns `false`. `list()` filters out deleted entries. But `stat()` still returns the entry with all version history intact.

### Wire format

The wire `VaultEntry` does not carry a `deleted` field. Deleted entries are simply not returned by listing or read operations at the service boundary. Access to deleted-but-persisted data requires explicit privileged queries.

---

## 6. Wire Format

When a VAULT entry crosses a service boundary (spine-to-spine communication, REST API, WebSocket), it uses the `VaultEntry` type defined in `zeos-types`.

### JSON Schema

Source: `/home/z13/zeos-types/schemas/vault_entry.schema.json`

```json
{
  "title": "VaultEntry",
  "type": "object",
  "properties": {
    "path":         { "type": "string" },
    "tier":         { "type": "string", "enum": ["sovereign", "internal", "reference"] },
    "entry_type":   { "type": "string", "enum": ["file", "directory", "signal", "link"] },
    "version":      { "type": "integer", "minimum": 0 },
    "data_id":      { "type": "string" },
    "size":         { "type": "integer", "minimum": 0 },
    "timestamp":    { "type": "integer", "minimum": 0 },
    "prev_version": { "type": ["integer", "null"] }
  },
  "required": ["path", "tier", "entry_type", "version"]
}
```

### Python wire type

Source: `/home/z13/zeos-types/python/zeos_types/vault_entry.py`

```python
class VaultEntry(BaseModel):
    path: str
    tier: Literal["sovereign", "internal", "reference"] = "internal"
    entry_type: Literal["file", "directory", "signal", "link"] = "file"
    version: int = 0
    data_id: str = ""
    size: int = 0
    timestamp: int = 0
    prev_version: int | None = None
```

### Mapping from implementations to wire type

| Wire field | C source | Rust source |
|---|---|---|
| `path` | Path string passed to API functions | `VaultEntry::path` |
| `tier` | `vault_inode.tier` (0/1/2 mapped to string) | `VaultEntry::tier` via `Tier::name()` |
| `entry_type` | `vault_inode.type` (1/2/3/4 mapped to string) | `VaultEntry::entry_type` |
| `version` | `vault_inode.version` | `Version::number` (latest) |
| `data_id` | N/A (block pointers are kernel-internal) | `Version::data_id` |
| `size` | `vault_inode.size` | `Version::size` |
| `timestamp` | `vault_inode.modified_tsc` (TSC cycles) | `Version::timestamp` (Unix epoch nanos) |
| `prev_version` | `vault_inode.prev_version` (inode number, 0 = none) | Index arithmetic on `versions` vec |

---

## 7. On-Disk Format

The same logical model (tiers, entries, version chains, soft delete) is stored differently depending on the runtime context.

### Z-OS kernel format (bare metal)

Layout: `Superblock -> Block bitmap -> Inode table -> Data blocks`

**Superblock** (`struct vault_super`, 4096 bytes):

| Field | Type | Description |
|---|---|---|
| `magic` | `uint32_t` | `0x564C5421` ("VLT!") |
| `version` | `uint32_t` | Format version (currently 1) |
| `block_size` | `uint32_t` | Always 4096 |
| `total_blocks` | `uint32_t` | Total blocks on device |
| `free_blocks` | `uint32_t` | Free block count |
| `inode_count` | `uint32_t` | Total inodes (default 1024) |
| `free_inodes` | `uint32_t` | Free inode count |
| `bitmap_start` | `uint32_t` | Block number of bitmap start |
| `inode_start` | `uint32_t` | Block number of inode table start |
| `data_start` | `uint32_t` | Block number of first data block |
| `root_inode` | `uint32_t` | Inode number of root directory (always 1) |
| `created_tsc` | `uint64_t` | TSC at format time |
| `mount_count` | `uint64_t` | Number of mounts |
| `label` | `uint8_t[32]` | Volume label |
| `_reserved` | `uint8_t[3960]` | Pad to 4096 bytes |

**Inode** (`struct vault_inode`, 128 bytes):

| Field | Type | Description |
|---|---|---|
| `type` | `uint32_t` | `VAULT_TYPE_*` |
| `tier` | `uint32_t` | `VAULT_TIER_*` |
| `size` | `uint32_t` | File size in bytes |
| `blocks` | `uint32_t` | Number of data blocks used |
| `direct[12]` | `uint32_t[12]` | Direct block pointers |
| `indirect` | `uint32_t` | Single indirect block pointer |
| `created_tsc` | `uint64_t` | TSC at creation |
| `modified_tsc` | `uint64_t` | TSC at last modification |
| `prev_version` | `uint32_t` | Inode number of previous version (0 = none) |
| `version` | `uint32_t` | Version counter |
| `owner_pid` | `uint32_t` | Owning process (for Internal tier) |
| `flags` | `uint32_t` | Permissions and flags |
| `_reserved` | `uint8_t[8]` | Pad to 128 bytes |

**Directory entry** (`struct vault_dirent`, 64 bytes):

| Field | Type | Description |
|---|---|---|
| `inode` | `uint32_t` | Inode number (0 = empty slot) |
| `name` | `char[60]` | Null-terminated name |

64 directory entries fit in one 4096-byte block.

Constants: `VAULT_BLOCK_SIZE` = 4096, `VAULT_MAX_NAME` = 60, `VAULT_MAX_PATH` = 256, `VAULT_INODE_COUNT` = 1024, `VAULT_DIRECT_BLOCKS` = 12.

### CFA-lib format (file-backed)

The Rust `Vault` stores metadata and data separately:

- **Metadata:** `vault.state` file (JSON-serialized `VaultState`) at the vault base path.
- **Data:** One `CfaStore` directory per tier (`sovereign/`, `internal/`, `reference/`), each containing CFA's encrypted manifest and block-padded data files.

`VaultState` contains a `HashMap<String, VaultEntry>` keyed by normalized path (e.g., `"/sovereign/patient-001.json"`). Each `VaultEntry` carries the full `Vec<Version>` chain. Each `Version` holds a `data_id` that maps to a blob in the tier's `CfaStore`.

Path normalization: all paths are prefixed with the tier name. `normalize_path("file.txt", Tier::Sovereign)` produces `"/sovereign/file.txt"`.

---

## 8. API Mapping Table

| Operation | C function | Rust method | Wire operation |
|---|---|---|---|
| Format | `vault_format(void *base, uint64_t size, const char *label)` | `Vault::format(base_path: &Path, label: &str, use_tpm: bool)` | N/A (local only) |
| Mount | `vault_mount(void *base, uint64_t size)` | `Vault::mount(base_path: &Path)` | N/A (local only) |
| Create | `vault_create(const char *path, uint32_t tier) -> int` | `Vault::create(&mut self, path: &str, tier: Tier)` | `POST /vault/{path}` |
| Write | `vault_write(const char *path, const void *data, uint32_t size) -> int` | `Vault::write(&mut self, path: &str, tier: Tier, data: &[u8]) -> Result<u32>` | `PUT /vault/{path}` |
| Read | `vault_read(const char *path, void *buf, uint32_t size) -> int` | `Vault::read(&self, path: &str, tier: Tier) -> Result<Vec<u8>>` | `GET /vault/{path}` |
| Read version | `vault_read_version(const char *path, void *buf, uint32_t size, uint32_t version) -> int` | `Vault::read_version(&self, path: &str, tier: Tier, version_back: u32) -> Result<Vec<u8>>` | `GET /vault/{path}?version={N}` |
| Append | `vault_append(const char *path, const void *data, uint32_t size) -> int` | `Vault::append(&mut self, path: &str, tier: Tier, data: &[u8])` | `PATCH /vault/{path}` |
| Delete | `vault_delete(const char *path) -> int` | `Vault::delete(&mut self, path: &str, tier: Tier)` | `DELETE /vault/{path}` |
| List | `vault_list(const char *path, struct vault_dirent *entries, int max_entries) -> int` | `Vault::list(&self, path: &str, tier: Tier) -> Result<Vec<&VaultEntry>>` | `GET /vault/{path}/` |
| Exists | `vault_exists(const char *path) -> int` | `Vault::exists(&self, path: &str, tier: Tier) -> bool` | `HEAD /vault/{path}` |
| Size | `vault_size(const char *path) -> int` | Via `VaultEntry.versions.last().size` | Included in `GET` response metadata |
| Stat | `vault_stat(uint32_t*, uint32_t*, uint32_t*, uint32_t*)` | `Vault::stat(&self, path: &str, tier: Tier) -> Result<&VaultEntry>` | `GET /vault/{path}?meta=true` |
| Stats | `vault_stat(...)` (filesystem-level) | `Vault::stats(&self) -> VaultStats` | `GET /vault/_stats` |
| History | Walk `prev_version` chain | `Vault::history(&self, path: &str, tier: Tier) -> Result<&[Version]>` | `GET /vault/{path}?history=true` |
| Sync | `vault_sync(void)` | `Vault::save_state(&self)` (called internally after every mutation) | N/A (local only) |

### Return conventions

- **C:** Returns `int`. Negative = error (`-1`). Non-negative = success (bytes read/written, inode number, entry count, or `0`/`1` for boolean).
- **Rust:** Returns `Result<T, VaultError>`. Errors are typed: `NotFound`, `AlreadyExists`, `NotAFile`, `NotADirectory`, `Deleted`, `VersionNotFound`, `Store`, `Io`, `Serde`.
- **Wire:** HTTP status codes. `200` = success. `201` = created. `404` = not found. `409` = already exists. `410` = deleted. Response body is JSON per the `VaultEntry` schema.
