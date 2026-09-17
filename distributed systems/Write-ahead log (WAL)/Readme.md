# Write-ahead log (WAL)

<sub>[Back to Distributed Systems](../Readme.md#content)</sub>

**A write-ahead log (WAL) records changes durably before the database writes those changes into its main data files.** If a crash interrupts the data-file writes, the database can reconstruct missing changes from the log. A transaction can therefore become durable without immediately saving every page it changed.

Start with the memory and storage layout, follow a transaction through commit and checkpointing, then examine crash recovery and the limits of the guarantee. The main example uses PostgreSQL 18 with synchronous local commit and reliable storage; other engines share the idea but implement it differently.

## The pieces you need to know

| Term | Meaning |
|---|---|
| Transaction | A group of operations that commits as one unit or is rolled back. |
| Data page | A fixed-size block in a database file, containing table or index data. |
| Buffer pool | Memory holding copies of data pages. A **dirty page** has changes that have not yet been written back to its data file. |
| WAL record | Information the engine uses to recover a change. It is not necessarily the original SQL statement. |
| Log sequence number (LSN) | A position in the log. In PostgreSQL it is a byte offset, useful for comparing recovery and replication progress. |
| Durable | Stored so it survives the failures covered by the storage guarantee, including power loss when synchronization works correctly. |
| REDO | Reapplying recorded changes during recovery. |
| Checkpoint | A recovery boundary established by persisting data and recording where recovery can safely begin. |

## Two representations of the same changes

Read the diagram from the client to the database engine. Memory holds working pages and buffered log records. Persistent storage holds the WAL and the main data files. The two storage boxes describe different roles; they do not require different physical disks.

![wal-storage-layout.svg](images/wal-storage-layout.svg)

The WAL describes changes in log order. Data files organize the database for access, such as table and index lookups. A recently committed change can already be recoverable from WAL while its data page on disk still contains an older state.

**“Write ahead” constrains persistent writes, not every change in memory.** Updating an in-memory page does not require a separate disk synchronization first. Before that dirty page is written to its data file, however, all WAL records needed to recover its changes must be durable.

## The two ordering rules

| Rule | Required ordering | Why it matters |
|---|---|---|
| Write-ahead rule | Make a page's WAL records durable **before** writing the changed data page. | Recovery has the information needed if the page write is interrupted. |
| Durable commit rule | Make the transaction's WAL durable **through its commit record before** reporting successful synchronous commit. | Acknowledged work can survive a crash even if the data files lag behind. |

Appending bytes to a memory buffer or handing them to the operating system is not necessarily enough. A synchronization operation, such as `fsync` or an equivalent supported mechanism, must establish persistence. The operating system, controller, and drive must honor that request.

## A transaction to follow

Suppose accounts A and B contain `100` and `50`. Transaction `T1` transfers `20`, producing `A = 80` and `B = 70`. Assume the two rows occupy different pages and there are no competing updates in this example.

The following SQL illustrates the transaction boundary; it assumes an existing `accounts` table and both account rows:

```sql
BEGIN;
UPDATE accounts SET balance = balance - 20 WHERE id = 'A';
UPDATE accounts SET balance = balance + 20 WHERE id = 'B';
COMMIT;
```

The next three sections follow one possible execution. Background page writes can overlap transaction execution; they do not universally wait for commit.

## Step 1 — Change memory and generate log records

![wal-buffer-changes.svg](images/wal-buffer-changes.svg)

Initially, the persisted balances are `100` and `50`. The updates change the working pages to `80` and `70`, making them dirty, and generate WAL records describing the changes. Records may initially be buffered in memory.

At this stage, the transaction has not received a successful commit response. The changed pages alone cannot provide durability because memory disappears on a crash. PostgreSQL's transaction visibility rules also prevent another transaction from treating these unfinished changes as committed.

The diagram deliberately separates log generation from log persistence: a record's existence in memory is not proof that recovery will find it.

## Step 2 — Persist the commit before acknowledging success

![wal-durable-commit.svg](images/wal-durable-commit.svg)

When the client requests `COMMIT`, the engine records the commit and synchronizes the WAL through that record. This also covers the transaction's preceding change records. Only after successful synchronization does synchronous local commit return success.

Now `T1` is durable even if neither changed page has reached its data file. There is no requirement to checkpoint this transaction before acknowledging it.

**Group commit** lets one WAL synchronization cover several transactions whose commit records are included in the flushed range. It reduces synchronization work per transaction while each caller still waits for its own required WAL position to become durable.

## Step 3 — Persist pages and advance the recovery boundary

![wal-checkpoint.svg](images/wal-checkpoint.svg)

Background writing and checkpointing move dirty pages into the main data files. Every page write still obeys the write-ahead rule. In our execution, the balances on disk eventually become `80` and `70`.

A completed PostgreSQL checkpoint records a safe **redo starting position**. Recovery can start there instead of replaying the database's entire history. The checkpoint record stores this REDO location, which can point earlier in WAL than the checkpoint record itself because writes continue while checkpointing runs.

Old WAL becomes eligible for recycling only when no longer required. Crash recovery is not the only consumer: replication and archival requirements can retain older segments. A checkpoint therefore does not mean “delete the whole log.”

This step is not a universal commit prerequisite. A dirty page may even reach storage before its transaction commits, provided its WAL is already durable; transaction status determines whether those changes become visible.

## What happens after a crash?

Consider a crash after `T1` has a durable commit but before B's page is saved. Disk contains the new A page and the old B page. Recovery uses the checkpoint's redo starting position and the surviving WAL to restore the database to a consistent state.

![wal-crash-recovery.svg](images/wal-crash-recovery.svg)

The outcome depends on what survived, not just on what was in memory:

| State at failure | Outcome for the example |
|---|---|
| `T1` is unfinished, with no recoverable commit | Transaction-status rules prevent its incomplete changes from being exposed as committed data; physical page recovery is a separate concern. |
| `T1`'s changes and commit are durable; some data pages still have old contents | Recovery restores the committed result: `A = 80`, `B = 70`. Torn writes additionally require the protection described below. |
| The commit is durable, but the success response never reaches the client | The transfer can survive even though the client cannot tell whether it succeeded. |
| A checkpoint has already persisted the required state | Recovery needs only the remaining WAL from its recorded starting position. |

**Recovery is engine work, not an application rerunning the SQL transfer.** Blindly executing another debit could move money twice. The lost-response case therefore needs application-level handling, such as a unique transfer ID and a stored result that a retry can check.

WAL does not prescribe one universal undo algorithm. Physical recovery and transaction visibility are separate concerns: restoring recorded page changes is not permission to expose an unfinished transaction. PostgreSQL uses multiversion concurrency control (MVCC), which gives readers an appropriate snapshot of row versions, together with transaction status and locking.

### Interrupted page writes

A power failure can leave a **torn page**: part of a page reflects the new write while another part remains old. Incremental changes alone may not repair that damaged starting state. With `full_page_writes` enabled, PostgreSQL logs a full page image on its first modification after a checkpoint so recovery can reconstruct it. Reliable storage synchronization remains necessary.

## Why WAL helps performance

Committing several scattered data-page changes immediately would require synchronizing those pages. WAL concentrates the commit-critical work into an append-oriented log, while the engine can combine and spread out later page writes. Group commit shares synchronization cost across concurrent transactions.

The work does not disappear: the system writes log information, later writes data pages, and may log full page images. More frequent checkpoints can reduce recovery work but increase write pressure and full-page WAL traffic. Less frequent checkpoints leave more work for recovery. Actual latency depends on the storage, workload, and durability settings.

## How implementations differ

| Engine | What WAL protects | Important distinction |
|---|---|---|
| PostgreSQL | Changes needed to recover database pages and transaction state. | Data pages can be written separately from commit. WAL also supports physical replication and archived recovery. |
| SQLite in WAL mode | Changed pages appended to a separate WAL file. | Readers can obtain pages from both the database and WAL. Checkpointing transfers WAL content to the main database; there is one writer at a time. |
| RocksDB | Updates also held in an in-memory **memtable**. | Recovery rebuilds lost memtable contents from WAL. Once the data is flushed into sorted on-disk table files, the corresponding WAL can eventually be reclaimed. |

Do not transfer durability defaults between engines. For example, SQLite's `synchronous=FULL` synchronizes WAL at each commit; `NORMAL` can lose recent transactions after power loss. RocksDB's default WAL behavior provides process-crash consistency, which is not the same promise as surviving a machine failure with all recent writes.

## Guarantees and boundaries

- **Asynchronous commit changes the acknowledgment promise.** PostgreSQL can return success before WAL is durable, so a crash can lose recent acknowledged transactions. Recovery can still remain consistent. Disabling `fsync` is different and can permit corruption.
- **Local WAL does not create a remote copy.** Replication sends changes to another server. An asynchronous replica can lag behind an acknowledged local commit; failover may lose work it never received.
- **WAL is not a complete backup by itself.** PostgreSQL point-in-time recovery needs a suitable base backup and an unbroken sequence of archived WAL. It can stop replay at a chosen recovery target.
- **The storage must survive.** If the only data files and WAL are destroyed together, local crash recovery cannot reconstruct the database from nothing.
- **Isolation still needs concurrency control.** WAL's persistence ordering does not by itself decide which concurrent changes a reader may observe.

The key distinction to remember is **commit versus checkpoint**: commit establishes the transaction's durability promise; a checkpoint establishes a later recovery boundary by persisting accumulated state.

# Sources

- [PostgreSQL 18 — Write-Ahead Logging](https://www.postgresql.org/docs/18/wal-intro.html)
- [PostgreSQL 18 — Transactions](https://www.postgresql.org/docs/18/tutorial-transactions.html)
- [PostgreSQL 18 — WAL Internals](https://www.postgresql.org/docs/18/wal-internals.html)
- [PostgreSQL 18 — Reliability](https://www.postgresql.org/docs/18/wal-reliability.html)
- [PostgreSQL 18 — WAL Configuration](https://www.postgresql.org/docs/18/wal-configuration.html)
- [PostgreSQL 18 — Asynchronous Commit](https://www.postgresql.org/docs/18/wal-async-commit.html)
- [PostgreSQL 18 — Concurrency Control: Introduction](https://www.postgresql.org/docs/18/mvcc-intro.html)
- [PostgreSQL 18 — Log-Shipping Standby Servers](https://www.postgresql.org/docs/18/warm-standby.html)
- [PostgreSQL 18 — Continuous Archiving and Point-in-Time Recovery](https://www.postgresql.org/docs/18/continuous-archiving.html)
- [SQLite — Write-Ahead Logging](https://sqlite.org/wal.html)
- [RocksDB — Write Ahead Log](https://github.com/facebook/rocksdb/wiki/Write-Ahead-Log-%28WAL%29)
- [Amazon Builders' Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
