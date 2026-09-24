# Computer Science
<sub>[Back to Anki Flashcards](../README.md)</sub>

Anki-ready cards on general computer-science and interview-preparation topics, each with its own teaching diagrams.

Every card lives in its own folder as `Readme.md`, with its diagrams in a sibling `images/` directory.

## Content
 * [ACID vs BASE](./ACID%20vs%20BASE/Readme.md) — every ACID and BASE property, synchronous versus asynchronous replication, and the CAP theorem's partition trade-off.
 * [Cross-Site Request Forgery](./Cross-Site%20Request%20Forgery/Readme.md) - how a browser sends an attacker's action with the victim's session cookie, attack sequence diagrams, and CSRF defenses
 * [Data structures. Bloom filter](./Data%20structures.%20Bloom%20filter/Readme.md) - bit arrays and hashing, false positives without false negatives, and avoiding unnecessary database reads
 * [Data structures. Merkle tree](./Data%20structures.%20Merkle%20tree/Readme.md) - how a root hash summarizes a data set, isolates the one block two replicas disagree on, and proves a single block with an audit path
 * [Data structures. Ring buffer](./Data%20structures.%20Ring%20buffer/Readme.md) - fixed-array slot reuse, wraparound, queue operations, and full/empty handling
 * [Data structures. Trie](./Data%20structures.%20Trie/Readme.md) - what a trie is, word endings and prefix lookup, time and space complexity, and practical uses
 * [Encoded vs Encrypted](./Encoded%20vs%20Encrypted/Readme.md) - Base64 versus confidentiality, symmetric and asymmetric encryption, and what digital signatures verify
 * [Fundamental Principles of OOP](./Fundamental%20Principles%20of%20OOP/Readme.md) - encapsulation, abstraction, inheritance, and Java's forms of polymorphism: runtime dispatch, overloading, generics, and implicit conversions, with examples and teaching diagrams
 * [Multiversion concurrency control](./Multiversion%20concurrency%20control/Readme.md) - how one row becomes a chain of versions, how a snapshot picks the version a reader sees, where engines keep the old ones, and why write skew survives
 * [Non-functional requirements and how to test them](./Non-functional%20requirements%20and%20how%20to%20test%20them/Readme.md) - functional versus quality requirements, measurable targets, testing methods, and production examples
 * [p50 vs p95](./p50%20vs%20p95/Readme.md) - typical and slow-tail request latency, percentile cutoffs, and automatic measurement with k6 and Prometheus
 * [Protocols. FTP](./Protocols.%20FTP/Readme.md) - separate control and data connections, active/passive modes, and encryption
 * [Protocols. HTTP](./Protocols.%20HTTP/Readme.md) - requests, responses, status codes, statelessness, HTTPS, and protocol versions
 * [Protocols. HTTPS](./Protocols.%20HTTPS/Readme.md) - TLS handshakes, public/private and traffic keys, encrypted HTTP, and visible metadata
 * [Protocols. POP3 vs IMAP](./Protocols.%20POP3%20vs%20IMAP/Readme.md) - downloaded mail copies versus a shared mailbox synchronized across devices
 * [Protocols. SFTP](./Protocols.%20SFTP/Readme.md) - secure file operations over SSH, one protected connection, and differences from FTP and FTPS
 * [Protocols. SMTP](./Protocols.%20SMTP/Readme.md) - how email is submitted, relayed, and accepted for delivery
 * [Protocols. SOAP](./Protocols.%20SOAP/Readme.md) - XML envelopes, headers, bodies, faults, and the roles of WSDL and HTTP
 * [Protocols. SSE](./Protocols.%20SSE/Readme.md) - one HTTP response that never ends, the four wire-format fields, automatic reconnection with Last-Event-ID, and the five patterns built on top
 * [Protocols. SSH](./Protocols.%20SSH/Readme.md) - server verification, user authentication, and encrypted remote commands
 * [Protocols. WebSocket](./Protocols.%20WebSocket/Readme.md) - the upgrade handshake, frames and masking, what proxies and load balancers do to a long-lived connection, and the five patterns built on top
 * [REST naming convention](./REST%20naming%20convention/Readme.md) - how to name resources, collections, and actions in an HTTP API
 * [SOLID](./SOLID/Readme.md) - the five design principles, the problem each one solves, and how to spot a violation
 * [STAR](./STAR/Readme.md) - the situation, task, action, and result structure for behavioural interview answers
 * [Time Complexity](./Time%20Complexity/Readme.md) - how growth rates compare and what each one costs at scale
 * [Transaction isolation levels](./Transaction%20isolation%20levels/Readme.md) - lost updates, dirty and non-repeatable reads, phantoms, the four SQL isolation levels, and Oracle read-only transactions
 * [URI vs URL](./URI%20vs%20URL/Readme.md) - identification versus location, the URL subset, and concrete URL and URN examples
