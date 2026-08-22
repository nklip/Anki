# Docker Best Practices for Java Applications

## Front

What are the most important Docker best practices for building and running a production Java application?

## Back

A good Java container image should be:

- Reproducible and quick to rebuild.
- Small enough to reduce unnecessary packages and attack surface.
- Built without embedded credentials.
- Run as a non-root user.
- Correctly limited and sized for CPU and memory.
- Able to receive shutdown signals directly.
- Observable, disposable, and independent of local container storage.

### Production-oriented Maven example

```dockerfile
# syntax=docker/dockerfile:1

# Build stage: contains the JDK, Maven wrapper, sources, and build cache.
FROM eclipse-temurin:25-jdk AS build
WORKDIR /workspace

# Copy stable dependency descriptors before frequently changing sources.
COPY --chmod=0755 mvnw ./mvnw
COPY .mvn/ ./.mvn/
COPY pom.xml ./pom.xml

# Cache downloaded Maven artifacts between BuildKit builds.
RUN --mount=type=cache,target=/root/.m2 \
    ./mvnw -B -DskipTests dependency:go-offline

COPY src/ ./src/

# Use verify so tests act as a build gate.
RUN --mount=type=cache,target=/root/.m2 \
    ./mvnw -B verify

# Runtime stage: contains only a Java runtime and the application artifact.
FROM eclipse-temurin:25-jre AS runtime

RUN groupadd --system --gid 10001 javaapp \
    && useradd --system --uid 10001 --gid 10001 \
       --home-dir /app --shell /usr/sbin/nologin javaapp

WORKDIR /app

COPY --from=build --chown=10001:10001 \
    /workspace/target/app.jar /app/app.jar

USER 10001:10001

# Documentation only; publishing the port is a runtime decision.
EXPOSE 8080

# Exec form: the JVM is PID 1 and receives container signals directly.
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
```

Use an image version supported by the application. Java 25 is shown because it is the current LTS line; replace it deliberately when the application's support policy differs.

For production, choose a specific maintained OS variant and consider pinning the approved image to a digest. Automate digest updates so reproducibility does not prevent security patches.

### 1. Use multi-stage builds

The build image needs a JDK, build tool, source code, and caches. The runtime image normally needs only:

- A Java runtime.
- The application artifact.
- Required certificates, time-zone data, or native libraries.

Multi-stage builds keep compilers, Maven or Gradle caches, source files, tests, and temporary artifacts out of the production image.

```text
JDK build stage ──copies JAR/runtime──▶ minimal runtime stage
```

Do not install Maven or Gradle in the final stage merely to launch a JAR.

### 2. Choose a trusted, maintained runtime image

- Prefer a maintained Docker Official Image or another approved, traceable distribution.
- Use an explicit Java major version; avoid `latest`.
- Select a compatible OS family deliberately.
- Rebuild frequently to receive patched JDK and OS layers.
- Scan both application dependencies and the resulting image.

A smaller image can reduce unnecessary software, but size alone does not prove security. A maintained image with clear provenance is more important than chasing the smallest possible byte count.

Alpine-based Java images use `musl` instead of `glibc`. Test native libraries, DNS behavior, fonts, locale handling, and performance before changing OS families merely to reduce image size.

### JRE image versus `jlink`

Options for the runtime stage include:

1. A maintained JRE image — simple and broadly compatible.
2. A custom runtime made with `jlink` — potentially smaller, but module discovery, service providers, TLS, monitoring, and framework features must be tested carefully.

Do not remove modules blindly. A small image that fails during an unusual production code path is not an improvement.

### 3. Optimize layer caching

Copy files from least frequently changed to most frequently changed:

```text
wrapper and build descriptors
        ↓
download dependencies
        ↓
application source
        ↓
compile and package
```

If source code is copied before dependency resolution, every source edit can invalidate the expensive dependency layer.

BuildKit cache mounts accelerate downloads without copying the cache into the final image:

```dockerfile
RUN --mount=type=cache,target=/root/.m2 \
    ./mvnw -B verify
```

For Gradle, use the wrapper, a BuildKit cache mount for the Gradle user home, and normally `--no-daemon` during image builds.

### 4. Keep the build context small

Example `.dockerignore`:

```dockerignore
.git
.idea
.vscode
target
build
*.iml
*.log
.env
compose*.yml
README*
```

Do not send credentials, local build output, IDE metadata, or the complete Git history to the build daemon when they are unnecessary.

Use explicit `COPY` instructions. Avoid `COPY . .` when only a few known directories are required.

### 5. Never bake secrets into an image

Do not use `ARG`, `ENV`, copied files, or command-line text to embed repository passwords, API keys, private certificates, or tokens. Image history and layers can retain them even if a later layer deletes the file.

Use a BuildKit secret mount for a private Maven settings file:

```dockerfile
RUN --mount=type=secret,id=maven_settings,\
target=/root/.m2/settings.xml,required=true \
    --mount=type=cache,target=/root/.m2 \
    ./mvnw -B verify
```

```text
docker build \
  --secret id=maven_settings,src=/secure/path/settings.xml \
  -t example/orders:1.4.2 .
```

Provide runtime secrets through the deployment platform's secret mechanism. Prefer short-lived credentials and mounted secret files when possible.

### 6. Run as a non-root user

Use a dedicated user with a stable numeric UID and GID:

```dockerfile
USER 10001:10001
```

Create and assign ownership only to directories the application must write. Do not make the entire filesystem world-writable.

At runtime, add defense in depth where supported:

```text
--read-only
--tmpfs /tmp:rw,noexec,nosuid,size=64m
--cap-drop=ALL
--security-opt=no-new-privileges:true
```

If the application writes heap dumps, JFR recordings, uploads, or generated files, mount narrowly scoped writable paths. Test read-only operation before production.

### 7. Use exec-form `ENTRYPOINT`

Correct:

```dockerfile
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
```

Risky shell form:

```dockerfile
ENTRYPOINT java -jar /app/app.jar
```

The shell form normally makes `/bin/sh` PID 1. Signals may not reach the JVM as expected. With exec form, the JVM receives `SIGTERM` directly when Docker stops the container.

If a startup script is necessary, end it with `exec`:

```sh
exec java -jar /app/app.jar
```

Implement graceful shutdown and configure a stop timeout long enough for the application to:

- Stop accepting new work.
- Finish or cancel in-flight requests.
- Close consumers, executors, and connection pools.
- Flush telemetry.

If the Java process creates child processes, consider Docker's `--init` option so orphaned children and zombies are handled correctly.

### 8. Set runtime resource limits

Containers have no CPU or memory limit by default. Configure limits in Docker, Compose, Kubernetes, or the production scheduler:

```text
docker run --rm \
  --memory=768m \
  --cpus=1.5 \
  --pids-limit=256 \
  example/orders:1.4.2
```

Choose limits from load tests and production measurements. An unrealistically low PID limit can prevent the JVM from creating required native threads.

CPU limits affect more than application threads. They also influence:

- Garbage-collector worker counts.
- JIT compilation.
- `ForkJoinPool` parallelism.
- Parallel streams.

Test the application under the same limits used in production, not only on an unrestricted developer machine.

### 9. Size the JVM for total container memory

On Linux, modern HotSpot enables container detection by default and uses available container memory and processor information for JVM ergonomics.

Inspect what the JVM detects:

```text
java -XshowSettings:system -XshowSettings:vm -version
```

For detailed container detection diagnostics:

```text
-Xlog:os+container=trace
```

The Java heap is only part of the container's memory use:

```text
container memory
├── Java heap
├── metaspace
├── code cache
├── thread stacks
├── direct and mapped buffers
├── GC and JVM native structures
└── native libraries and agents
```

Therefore, do not set `-Xmx` equal to the container memory limit. Leave measured headroom for non-heap memory and traffic spikes.

Possible approaches:

```text
-Xmx512m
```

or:

```text
-XX:MaxRAMPercentage=65
```

The percentage is an example, not a universal recommendation. Select it from measurements of heap and non-heap usage. Avoid copying a fixed percentage into every service.

Supply environment-specific JVM options at deployment time when appropriate:

```text
JAVA_TOOL_OPTIONS=-XX:MaxRAMPercentage=65
```

Do not place secrets in `JAVA_TOOL_OPTIONS`; the JVM reports applied options at startup.

Use `-XX:ActiveProcessorCount` only when intentional override is necessary. Prefer accurate container CPU configuration instead of hiding a deployment error with JVM flags.

### 10. Keep the container disposable

- Store durable data in databases, object storage, or mounted volumes.
- Treat the container filesystem as temporary.
- Inject configuration at runtime rather than rebuilding for every environment.
- Do not persist session state only inside one container instance.
- Make startup, shutdown, and replacement routine operations.

An image should represent the application version. A running container should not modify its own binaries or download replacement application code.

### 11. Write logs to standard output and error

Write application logs to `stdout` and diagnostic/error output to `stderr`. Let the container platform collect, rotate, retain, and forward them.

Avoid writing unbounded log files inside the container. Local files consume writable-layer space and disappear when the container is replaced.

Never log secrets, session tokens, authorization headers, or sensitive personal data.

### 12. Add meaningful health signals

Expose a lightweight health endpoint that distinguishes, where the platform supports it:

- **Liveness** — should the process be restarted?
- **Readiness** — can it receive new traffic?
- **Startup** — is initialization still legitimately in progress?

Do not install a large shell or HTTP client only for a health check in an otherwise minimal image. The deployment platform can often probe the application endpoint from outside the container.

A health check should be fast, bounded by a timeout, and should not overload dependencies. Liveness should not fail merely because one downstream service is temporarily unavailable.

### 13. Make builds reproducible and auditable

- Use Maven or Gradle wrappers.
- Pin application dependencies through the build definition and lock mechanisms where available.
- Use explicit base-image versions; optionally pin approved digests.
- Record source revision and build metadata using OCI labels or provenance.
- Generate an SBOM and retain it with the image.
- Scan for known vulnerabilities in CI and after base-image updates.
- Rebuild instead of patching a running container.
- Test the final image, not only the JAR outside Docker.

Pinning a digest improves reproducibility but also freezes security fixes. Pair digest pinning with automated update pull requests and regular rebuilds.

### 14. Minimize installed software and privileges

- Do not include compilers, package managers, SSH servers, editors, or debugging agents unless production genuinely requires them.
- Prefer `COPY` for local files; use `ADD` only when its additional behavior is intentional.
- Avoid unnecessary OS packages.
- Do not expose remote-debugging or management ports publicly.
- Do not mount the Docker socket into an application container.
- Do not use `--privileged` for a normal Java service.

When a temporary debugging tool is necessary, prefer an ephemeral diagnostic container or a separately controlled debug image rather than permanently expanding the production image.

### 15. Test architecture and native compatibility

For multi-platform images, test every supported architecture, especially when using:

- JNI or JNA.
- Native compression, TLS, database, or image libraries.
- Fonts or headless rendering.
- Architecture-specific agents.
- A custom `jlink` runtime.

Building an ARM64 image successfully does not prove that all included native libraries support ARM64 correctly.

### Common anti-patterns

| Anti-pattern | Better approach |
|---|---|
| `FROM ...:latest` | Use an intentional version and update policy |
| Build and run in one JDK image | Use separate build and runtime stages |
| `COPY . .` before dependency download | Copy build descriptors first and use cache mounts |
| Secrets in `ARG`, `ENV`, or copied settings | Use BuildKit secret mounts and runtime secrets |
| Running as root | Use a dedicated numeric UID/GID |
| Shell-form Java entrypoint | Use JSON exec form or `exec` in the wrapper |
| `-Xmx` equal to container memory | Leave measured non-heap/native headroom |
| No CPU or memory limits | Configure and test realistic resource limits |
| Blocking only on `sleep` for readiness | Use bounded health and readiness checks |
| Logs only in container files | Write to `stdout` and `stderr` |
| Mutable local production state | Use external durable storage |
| Installing tools “just in case” | Keep production runtime minimal |
| Never rebuilding a pinned image | Automate updates, scanning, and rebuilds |

### Review checklist

```text
[ ] Multi-stage build
[ ] Maintained and intentionally versioned base image
[ ] Small .dockerignore and explicit COPY instructions
[ ] Dependency cache optimized
[ ] Tests executed in CI/build pipeline
[ ] No secrets in image layers or history
[ ] Non-root numeric UID/GID
[ ] Exec-form Java entrypoint
[ ] Graceful SIGTERM handling
[ ] CPU, memory, and PID limits tested
[ ] Heap leaves room for native/non-heap memory
[ ] Read-only filesystem tested where practical
[ ] Logs go to stdout/stderr
[ ] Readiness and liveness behavior defined
[ ] Image and Java dependencies scanned
[ ] SBOM/provenance retained
[ ] Replacement and rollback tested
```

### Key idea

> Build the application in a disposable JDK stage, run only the required artifact in a maintained minimal runtime, execute as a non-root PID 1, provide secrets and configuration externally, and size the JVM within measured container limits.

### Official references

- [Docker build best practices](https://docs.docker.com/build/building/best-practices/)
- [Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker build secrets](https://docs.docker.com/build/building/secrets/)
- [Docker build-cache optimization](https://docs.docker.com/build/cache/optimize/)
- [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/)
- [Dockerfile reference](https://docs.docker.com/reference/dockerfile/)
- [Java launcher and container options](https://docs.oracle.com/en/java/javase/26/docs/specs/man/java.html)
- [Eclipse Temurin Docker Official Image](https://hub.docker.com/_/eclipse-temurin)
