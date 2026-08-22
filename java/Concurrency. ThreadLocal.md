# ThreadLocal in Modern Java

## Front

What is `ThreadLocal`, how should it be used safely, and when should modern Java prefer `ScopedValue`?

## Back

`ThreadLocal<T>` associates a separate value with each thread that accesses it.

- Each thread sees its own value.
- The value is not automatically shared with other threads.
- `ThreadLocal` does not make the stored object thread-safe if that object is published elsewhere.

### Basic API

```java
private static final ThreadLocal<String> REQUEST_ID = new ThreadLocal<>();

REQUEST_ID.set("request-123");
String id = REQUEST_ID.get();
REQUEST_ID.remove();
```

An initial value can also be supplied:

```java
private static final ThreadLocal<Integer> COUNTER =
        ThreadLocal.withInitial(() -> 0);
```

### Safe use with platform-thread pools

Pool threads are reused for many tasks. If a task does not remove its value, a later task on the same thread may observe stale data, and referenced objects may stay in memory unnecessarily.

```java
private static final ThreadLocal<String> REQUEST_ID = new ThreadLocal<>();

void handleRequest(String requestId) {
    try {
        REQUEST_ID.set(requestId);
        processRequest();
    } finally {
        REQUEST_ID.remove();
    }
}
```

Always put `remove()` in `finally` when a value is installed temporarily on a reusable thread.

### Appropriate uses

- Supporting a framework or legacy API that expects thread-local context.
- Keeping genuinely per-thread state that must be mutable.
- Request IDs, tracing data, or logging context when the surrounding library uses `ThreadLocal`.

### Avoid using it for

- Communication or synchronization between threads.
- Hiding ordinary method inputs when passing a parameter is clearer.
- Caching an expensive resource for every virtual thread.
- Assuming a value follows work that moves to a different thread.

### Virtual threads — Java 21+

Virtual threads support `ThreadLocal`, but an application may create a very large number of virtual threads. A separate value for every virtual thread can therefore consume substantial memory.

Do not use `ThreadLocal` to pool expensive resources such as database connections. Virtual threads should normally represent individual tasks rather than be pooled. Use a bounded resource pool or semaphore when access to a scarce resource must be limited.

The JDK can report when virtual threads set thread-local values:

```text
-Djdk.traceVirtualThreadLocals=true
```

### Prefer ScopedValue for bounded context — Java 25+

Use `ScopedValue` when context should be installed for a bounded operation, read by callees, and then automatically disappear.

```java
private static final ScopedValue<String> REQUEST_ID =
        ScopedValue.newInstance();

void handleRequest(String requestId) {
    ScopedValue.where(REQUEST_ID, requestId)
            .run(() -> processRequest());
}

void processRequest() {
    String id = REQUEST_ID.get();
}
```

The binding cannot be changed by called methods and is automatically restored when the operation finishes, including when an exception is thrown. Prefer immutable values as the bound data.

| `ThreadLocal` | `ScopedValue` |
|---|---|
| Value can be changed with `set()` | Binding is immutable inside its scope |
| Lifetime can be unbounded | Lifetime is bounded by the operation |
| Temporary values require `remove()` | Binding is removed automatically |
| Useful for mutable per-thread state and legacy APIs | Preferred for one-way context propagation |

### Key idea

Use `ThreadLocal` for truly thread-local mutable state or compatibility with existing APIs, and clean it up with `remove()` in `finally` on reusable threads. For immutable request context in Java 25+, prefer `ScopedValue`.

## Official references

- [ThreadLocal API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/lang/ThreadLocal.html)
- [Thread-local variables guide](https://docs.oracle.com/en/java/javase/26/core/thread-local-variables.html)
- [JEP 444: Virtual Threads](https://openjdk.org/jeps/444)
- [ScopedValue API](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/ScopedValue.html)
