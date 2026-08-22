# JVM Memory Organization: Heap, Stack, Metaspace, and GC

## Front

How is memory organized in a modern JVM?

Explain:

- The Java heap.
- Per-thread stacks and stack frames.
- HotSpot Metaspace.
- The JVM method area.
- Code cache and off-heap/native memory.
- How garbage collection interacts with these areas.
- The important virtual-thread exception.

## Back

JVM memory is not one single pool.

A useful first distinction is:

```text
shared memory                         per-thread execution state
──────────────────────────────────    ──────────────────────────
Java heap                             JVM stack / frames
method-area data                      pc register
HotSpot Metaspace                     native stack, if used
code cache
JVM and application native memory
```

The **JVM specification** defines logical runtime data areas. **HotSpot** chooses concrete implementations such as Metaspace and the code cache.

![Overall HotSpot and JVM memory organization](svg/jvm-memory-organization.svg)

## Specification model vs. HotSpot implementation

The JVM specification defines:

- `pc` register for each JVM thread.
- JVM stack for each JVM thread.
- Shared heap.
- Shared method area.
- Per-class runtime constant pools within the method area.
- Native method stacks when required by the implementation.

The specification deliberately does not prescribe exact addresses, physical layout, collector design, or whether every logical area occupies one contiguous block.

HotSpot commonly implements the process using areas including:

- Java heap.
- Metaspace and optional compressed class space.
- Code cache.
- Platform-thread native stacks.
- GC data structures.
- Direct and mapped memory.
- JVM, JNI, native-library, and allocator memory.

Therefore:

> The JVM method area is a specification concept. HotSpot Metaspace implements much of its class-metadata role, but the two terms are not universally interchangeable.

## Java heap

The **heap** is shared by all threads and is the primary memory area managed by the garbage collector.

Conceptually, it contains:

- Ordinary class instances.
- Arrays, including primitive arrays.
- `Class` mirror objects.
- Interned strings and ordinary `String` objects.
- Collection nodes and backing arrays.
- Virtual-thread stack-chunk objects.

```java
Customer customer = new Customer("Ana");
```

Conceptually:

```text
thread stack                          heap
────────────                          ────
local customer ─────────────────────▶ Customer object
                                      └── name ─────▶ String "Ana"
```

The local variable contains a **reference**. The referenced object is normally represented in the heap.

HotSpot may eliminate an allocation or replace an object with scalar values through escape analysis. That is an implementation optimization, not a Java-level guarantee that ordinary objects live in stack memory.

### Heap sizing

Common HotSpot options:

```text
-Xms<size>   initial/minimum heap sizing target
-Xmx<size>   maximum Java heap size
```

Examples:

```text
-Xms512m
-Xmx2g
```

`-Xmx` limits the Java heap, not the JVM process's total resident memory.

### Heap layout depends on the collector

Do not assume that every collector uses one fixed contiguous diagram of Eden, Survivor, and Old spaces.

- Serial and Parallel collectors have traditional generational layouts.
- G1 divides the heap into equal-sized regions whose roles can change.
- Modern ZGC is generational but organizes memory in collector-specific pages and metadata.

The public mental model is **objects in a GC-managed shared heap**. The physical organization is collector-dependent.

### Heap exhaustion

If the JVM cannot satisfy an object or array allocation after attempting the permitted collection and expansion work, it can throw:

```text
java.lang.OutOfMemoryError: Java heap space
```

This can mean:

- The live data genuinely requires more heap.
- A memory leak retains objects unintentionally.
- Allocation rate is too high for the configured collector and heap.
- Heap sizing is inappropriate for the workload.

## JVM stacks

Each executing thread has its own logical JVM stack. A method invocation creates a **frame**.

A frame contains data such as:

- Local variables.
- Primitive values and object references.
- Operand stack used by bytecode instructions.
- Information needed for dynamic linking.
- Method return and exception-handling state.

Example:

```java
static int total(Order order, int tax) {
    int subtotal = order.subtotal();
    return subtotal + tax;
}
```

Conceptually, the active frame contains:

```text
Frame: total(Order, int)
├── local 0: order reference ─────────▶ Order object in heap
├── local 1: tax primitive value
├── local 2: subtotal primitive value
├── operand stack
└── return/linkage information
```

### Frame lifetime

```text
method called  → frame pushed
method returns → frame popped
thread exits   → its remaining execution state disappears
```

GC does not sweep obsolete stack frames. Stack space is reused automatically as frames are popped.

References in active platform-thread frames are important **GC roots**. Their reachable heap objects must remain alive.

### Stack overflow

Deep or infinite recursion can exhaust the permitted stack depth:

```java
static void recurse() {
    recurse();
}
```

Result:

```text
java.lang.StackOverflowError
```

For platform threads, HotSpot stack sizing is commonly controlled with:

```text
-Xss<size>
```

Increasing it permits deeper stacks but raises the native-memory cost of each platform thread and can reduce the number of threads the process can create.

### Platform threads vs. virtual threads

A platform thread is backed by an operating-system thread and normally has a native thread stack.

A virtual thread is different:

- It is not permanently tied to one OS thread.
- It mounts on a platform **carrier thread** while running.
- Its stack is stored in the Java heap as stack-chunk objects.
- Its stack grows and shrinks rather than reserving one large native stack per virtual thread.

Therefore, millions of virtual threads do not imply millions of large native thread stacks. Their stack chunks do, however, contribute to heap occupancy and GC work.

## Method area

The JVM specification defines one shared **method area** containing per-class structures such as:

- Runtime constant pool.
- Field and method information.
- Method and constructor code representation.
- Class and interface initialization information.

The specification does not require the method area to be located in the Java heap, nor does it require a particular garbage-collection or compaction policy for it.

## HotSpot Metaspace

**Metaspace** is HotSpot's native-memory allocator for class metadata.

Since JDK 8, HotSpot stores class metadata in native memory rather than the old permanent generation, or **PermGen**.

Metaspace contains VM metadata describing loaded classes, for example:

- Internal class structures.
- Method metadata and bytecode-related metadata.
- Runtime constant-pool metadata.
- Field, annotation, and class-loader-associated metadata.

It does **not** mean “all non-heap memory.”

The following are separate:

- JIT-compiled native code in the code cache.
- Platform-thread stacks.
- Direct-buffer backing memory.
- Native libraries and application native allocations.
- GC bookkeeping structures.

### Class mirror vs. class metadata

For a loaded class such as `Customer`:

```text
heap                              Metaspace
────                              ─────────
java.lang.Class<Customer>  ─────▶ HotSpot class metadata
Customer instances               methods, fields, constant-pool metadata
```

The `Class` mirror is a normal heap object. HotSpot's internal class metadata is in Metaspace.

### Per-class-loader allocation

Metaspace uses arenas associated with class loaders. A class loader allocates metadata from its chunks.

Classes are normally unloaded as a group when their defining class loader and its classes become unreachable and the collector performs class unloading.

This explains a common leak pattern:

```text
unexpected strong reference to old ClassLoader
        ↓
old classes remain loaded
        ↓
their Metaspace remains retained
```

### Metaspace sizing

Important options:

```text
-XX:MaxMetaspaceSize=<size>
-XX:MetaspaceSize=<size>
```

`MaxMetaspaceSize` is an optional upper bound on class-metadata memory.

`MetaspaceSize` is primarily the initial high-water mark that influences when metadata pressure induces a GC. It is not simply “the initial amount of Metaspace allocated.”

With compressed class pointers enabled, HotSpot also uses a logically separate compressed class space:

```text
-XX:CompressedClassSpaceSize=<size>
```

### Metaspace exhaustion

If class metadata cannot be allocated, HotSpot can report:

```text
java.lang.OutOfMemoryError: Metaspace
```

Common causes include:

- Loading an unbounded number of generated classes.
- Retaining class loaders after redeployment.
- A configured `MaxMetaspaceSize` that is too small.
- Native-address-space or commit exhaustion.

Raising the limit may hide a class-loader leak, so inspect class-loader retention before treating the limit as the only problem.

## Code cache

HotSpot stores JIT-compiled native machine code in the **code cache**.

```text
bytecode + runtime profiles
            ↓ JIT
compiled native methods in code cache
```

The code cache is not the Java heap and is not Metaspace.

It also contains supporting generated code such as runtime stubs and adapters.

Code-cache pressure can cause compiled methods to be reclaimed or compilation behavior to change. It is observed and tuned separately from ordinary heap occupancy.

## Native and off-heap memory

Other process memory can include:

- Platform-thread stacks.
- Direct `ByteBuffer` backing memory.
- Memory-mapped files.
- Foreign Function and Memory API segments.
- JNI and native-library allocations.
- GC remembered sets, mark bitmaps, forwarding metadata, and worker structures.
- JIT/compiler data structures.
- Shared libraries and executable mappings.

This is why:

```text
process RSS > -Xmx
```

is normal.

An application can suffer native-memory exhaustion even while the Java heap has free space.

## How GC interacts with memory

![GC roots, heap reachability, and class unloading](svg/jvm-gc-roots-and-reclamation.svg)

At a high level, tracing collectors perform these logical steps:

```text
GC roots
   ↓
trace reachable heap objects
   ↓
mark live objects
   ↓
reclaim unreachable memory
   ↓
optionally move/compact live objects and repair references
```

Exact phases and concurrency differ by collector.

### Typical GC roots

Roots can include:

- References in active platform-thread stack frames and registers.
- Static/class-associated references kept through JVM class structures.
- JNI global and local handles.
- JVM-internal handles.
- Active monitors and synchronization structures.
- Collector-specific roots such as remembered-set entries or code roots.

Virtual-thread stacks are heap objects and are integrated with collector-specific scanning rather than behaving like one traditional native stack root each.

### Heap reclamation

A heap object is eligible for collection when it is no longer reachable through the collector's root and reference-processing rules.

```java
Customer customer = new Customer();
customer = null;
```

Setting the local to `null` does not immediately free the object. It only removes one reference. The object becomes collectible only if no relevant path can still reach it, and memory is reclaimed when the collector performs the necessary work.

Different collectors may:

- Copy or evacuate live objects.
- Compact in place.
- Reclaim whole regions or pages.
- Perform marking and relocation concurrently.
- Use brief or long stop-the-world phases.

### Stack reclamation

Stacks are not normally garbage-collected like the Java heap:

- Returning from a method pops its frame.
- Ending a platform thread releases its thread-stack resources.
- Virtual-thread stack chunks are heap objects and therefore participate in heap management.

### Metaspace reclamation

GC can indirectly reclaim Metaspace through **class unloading**:

```text
class loader becomes unreachable
        ↓
its classes become unloadable
        ↓
GC performs class unloading
        ↓
loader's metadata chunks are recycled or returned to the OS
```

Metaspace pressure can itself induce a collection when the metadata high-water mark is reached.

Class unloading is not the same as collecting an ordinary instance of a class. Millions of dead `Customer` instances can be reclaimed while the `Customer` class remains loaded.

## Example: where the values go

```java
final class OrderService {
    private static final TaxRules RULES = new TaxRules();

    Receipt place(Order order) {
        int attempts = 1;
        Receipt receipt = new Receipt(order, RULES);
        return receipt;
    }
}
```

Conceptually:

| Value | Typical logical location |
|---|---|
| `attempts` primitive local | Current stack frame |
| `order` local reference | Current stack frame |
| `Order` instance | Heap |
| `receipt` local reference | Current stack frame |
| `Receipt` instance | Heap |
| `RULES` referenced `TaxRules` object | Heap |
| `OrderService` class metadata | Metaspace in HotSpot |
| `OrderService.class` mirror | Heap |
| JIT-compiled `place()` machine code | Code cache |

This table is a conceptual model. JIT optimizations may remove, split, inline, or keep values in CPU registers while preserving Java semantics.

## Failure symptoms by area

| Symptom | Likely area or resource |
|---|---|
| `StackOverflowError` | One thread's stack depth |
| `OutOfMemoryError: Java heap space` | Java heap |
| `OutOfMemoryError: Metaspace` | Class metadata / native memory |
| `OutOfMemoryError: Compressed class space` | Compressed class metadata area |
| `OutOfMemoryError: unable to create native thread` | Native thread or process resources |
| Direct-buffer allocation failure | Direct/off-heap memory or configured direct-memory limit |
| Process killed by container or OS | Total process memory, not necessarily heap alone |

Always diagnose the exact message and memory category before changing JVM limits.

## Useful diagnostics

### Heap and GC

```text
jcmd <pid> GC.heap_info
jcmd <pid> GC.class_histogram
jcmd <pid> GC.heap_dump filename=heap.hprof
```

GC logging:

```text
-Xlog:gc*
```

### Native memory

Start with Native Memory Tracking when needed:

```text
-XX:NativeMemoryTracking=summary
```

Inspect it:

```text
jcmd <pid> VM.native_memory summary
```

Native Memory Tracking observes HotSpot-managed categories but does not account for every third-party native allocation.

### Class loading

```text
jcmd <pid> VM.classloader_stats
jcmd <pid> GC.class_histogram
-Xlog:class+load=info,class+unload=info
```

## Common misconceptions

### “Local objects are stored on the stack”

Usually false. The local variable may be a stack reference to a heap object. Escape analysis can optimize representation, but code must not depend on it.

### “Metaspace is part of the Java heap”

False for HotSpot. Class metadata is allocated in native memory.

### “Everything outside the heap is Metaspace”

False. Thread stacks, code cache, direct memory, GC structures, native libraries, and other native allocations are separate consumers.

### “The method area and Metaspace are identical JVM concepts”

False. Method area is specified by the JVM specification; Metaspace is a HotSpot implementation mechanism for class metadata.

### “GC cleans the stack”

Ordinary platform-thread frames are pushed and popped automatically. GC traces references from active frames but does not sweep frames like heap objects.

### “GC only affects the heap”

Ordinary object reclamation is a heap function, but GC can also unload classes and release their Metaspace metadata. GC also consumes native metadata and worker memory itself.

### “`-Xmx` is the process memory limit”

False. It limits the Java heap. A container or OS limit must also accommodate Metaspace, code cache, stacks, direct buffers, GC structures, and native code.

### “Calling `System.gc()` immediately frees everything unreachable”

False. It is a request, and collector policy or JVM options may ignore or handle it differently. Reference processing, class unloading, native cleaners, and OS memory return have separate rules.

## Summary

```text
Java heap
    shared, GC-managed objects and arrays
    bounded mainly by -Xms / -Xmx

Platform-thread stack
    private frames, locals, operand stacks, references
    native resource; commonly influenced by -Xss

Virtual-thread stack
    represented by heap stack-chunk objects
    mounted on a carrier while executing

Method area
    JVM-spec logical per-class storage

HotSpot Metaspace
    native class-metadata storage
    reclaimed mainly through class unloading

Code cache
    JIT-compiled native machine code

GC
    traces from roots, retains reachable heap objects,
    reclaims unreachable heap memory, and may unload classes

-Xmx is not total process memory.
JVM memory organization is not the Java Memory Model.
```

## Official references

- [JVM Specification 25 — Runtime Data Areas](https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-2.html#jvms-2.5)
- [Oracle Java 26 GC Tuning Guide — Class Metadata](https://docs.oracle.com/en/java/javase/26/gctuning/other-considerations.html)
- [JEP 387: Elastic Metaspace](https://openjdk.org/jeps/387)
- [JEP 444: Virtual Threads — Memory and GC](https://openjdk.org/jeps/444)
- [Oracle Java 25 — Native Memory Tracking](https://docs.oracle.com/en/java/javase/25/vm/native-memory-tracking.html)
- [Oracle Java 25 — Troubleshooting Memory Leaks and OOME](https://docs.oracle.com/en/java/javase/25/troubleshoot/troubleshooting-memory-leaks.html)
