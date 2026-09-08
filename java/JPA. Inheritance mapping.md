# JPA. Inheritance mapping

<!-- Card mode: complex. Validate with --mode complex. -->

## Front

How does JPA store an entity inheritance hierarchy?

Explain `SINGLE_TABLE`, `JOINED`, and `TABLE_PER_CLASS`: their tables, annotations, polymorphic queries, trade-offs, and the difference between an entity hierarchy and `@MappedSuperclass`.

## Back

JPA maps one entity hierarchy with `@Inheritance` on its **root entity**:
- `SINGLE_TABLE` uses one table and a discriminator
- `JOINED` splits one object across related tables
- `TABLE_PER_CLASS` gives every concrete entity a complete table.

A query of the root entity is polymorphic—it also returns its entity subtypes.

Start with the domain model, then choose the database shape that best matches the important queries and constraints.

### Vocabulary first

- **Root entity:** the first `@Entity` in the hierarchy; it declares `@Inheritance` and owns the identifier mapping.
- **Concrete entity:** a non-abstract entity that can be instantiated and stored.
- **Discriminator:** a column value such as `CARD` that identifies which subtype a row represents.
- **Polymorphic query:** a query of a base entity type that includes instances of its entity subclasses.

The examples use an abstract `Payment` root with `id` and `amount`, plus two concrete subtypes: `CardPayment` with `cardLast4` and `WirePayment` with `bankCode`.

The root owns `id`; entity subclasses inherit it. Put `@Inheritance` on `Payment`, not on every subtype. If the annotation or its `strategy` is omitted, JPA defaults to `SINGLE_TABLE`.

### `SINGLE_TABLE`: one table plus a type marker

All root and subtype fields become columns of one table. Each object uses exactly one row. The discriminator tells JPA whether that row is a `CardPayment` or `WirePayment`.

![jpa-inheritance-single-table.svg](svg/jpa-inheritance-single-table.svg)

```java
@Entity
@Table(name = "payment")
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
@DiscriminatorColumn(name = "payment_kind")
public abstract class Payment {
    // id and amount
}

@Entity
@DiscriminatorValue("CARD")
public class CardPayment extends Payment {
    // cardLast4
}

@Entity
@DiscriminatorValue("WIRE")
public class WirePayment extends Payment {
    // bankCode
}
```

If a required discriminator column is not configured, its portable defaults are name `DTYPE` and type `STRING`. For a string discriminator, the default value is the entity name, but explicit stable values avoid coupling stored data to a renamed entity.

Why choose it:

- A root query normally reads one table; Hibernate does not need subtype joins.
- Inserts and subtype loads touch one table.
- It is required for every compliant JPA provider and is the default strategy.

Costs:

- Subtype-only columns are unused for other types, so they must be nullable at the column level.
- A large hierarchy can create a wide, sparse table.
- Subtype-specific invariants often need database `CHECK` constraints, triggers, or application validation instead of a simple `NOT NULL`.

### `JOINED`: normalized tables connected by the same ID

The root table stores inherited fields. Each subtype table stores its own fields, and its primary key is also a foreign key to the corresponding root row. A `CardPayment` therefore occupies one `payment` row **and** one `card_payment` row.

![jpa-inheritance-joined.svg](svg/jpa-inheritance-joined.svg)

```java
@Entity
@Table(name = "payment")
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class Payment {
    // id and amount
}

@Entity
@Table(name = "card_payment")
@PrimaryKeyJoinColumn(name = "payment_id")
public class CardPayment extends Payment {
    // cardLast4
}

@Entity
@Table(name = "wire_payment")
@PrimaryKeyJoinColumn(name = "payment_id")
public class WirePayment extends Payment {
    // bankCode
}
```

`@PrimaryKeyJoinColumn` customizes the subtype join column; it is not required when the default column mapping is suitable. A discriminator is not required for `JOINED`, because matching subtype rows can reveal the concrete type.

Why choose it:

- Shared columns exist once, and the schema mirrors the class hierarchy.
- Subtype columns can use subtype-specific `NOT NULL`, unique, and check constraints.
- It is required for every compliant JPA provider.

Costs:

- Loading a subtype requires at least one join with its parent table.
- Inserting or deleting one subtype touches multiple tables.
- In Hibernate, a root query commonly left-joins the subtype tables; deep or wide hierarchies can produce expensive SQL.

### `TABLE_PER_CLASS`: one complete table per concrete entity

Every concrete subtype has its own table containing both inherited and subtype-specific columns. With an abstract `Payment`, there is no `payment` row shared by the two concrete types.

![jpa-inheritance-table-per-class.svg](svg/jpa-inheritance-table-per-class.svg)

```java
@Entity
@Inheritance(strategy = InheritanceType.TABLE_PER_CLASS)
public abstract class Payment {
    // id and amount
}

@Entity
@Table(name = "card_payment")
public class CardPayment extends Payment {
    // inherited id and amount, plus cardLast4
}

@Entity
@Table(name = "wire_payment")
public class WirePayment extends Payment {
    // inherited id and amount, plus bankCode
}
```

Why choose it:

- Reading one known concrete type needs only its table.
- Each concrete table can enforce constraints appropriate to that type.
- No irrelevant subtype columns and no parent-row join are needed.

Costs:

- Inherited columns and indexes are duplicated; changing a base mapping can require changes to every concrete table.
- A foreign key to the abstract root is difficult to represent as one ordinary database foreign key.
- Hibernate implements a root query with a `UNION`-style derived table, which gets more expensive as the hierarchy grows.
- **Portability warning:** Jakarta Persistence 3.2 makes provider support for this strategy optional.

Use it only after checking provider support and query plans; it fits small hierarchies queried mainly by concrete type.

### One JPQL query, three SQL shapes

The JPQL stays the same because `Payment` is an entity:

```java
List<Payment> payments = entityManager.createQuery(
        "select p from Payment p order by p.id",
        Payment.class
).getResultList();
```

It can return both `CardPayment` and `WirePayment`. The provider translates that semantic query to the chosen mapping:

| Strategy | Rows that represent one subtype object | Typical Hibernate root-query shape |
|---|---:|---|
| `SINGLE_TABLE` | One row in one hierarchy table | One table scan; inspect discriminator |
| `JOINED` | Root row + subtype row | Root table with joins to subtype tables |
| `TABLE_PER_CLASS` | One row in its concrete table | Union of concrete tables |

SQL shape is provider- and database-dependent; use generated SQL and real execution plans for performance decisions.

### `@MappedSuperclass` is reuse, not entity polymorphism

A mapped superclass contributes mappings to its entity subclasses but is **not** an entity, has no separate table, and cannot be queried or passed to `EntityManager` operations as an entity type.

```java
@MappedSuperclass
public abstract class AuditedEntity {
    @Id
    @GeneratedValue
    private Long id;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;
}

@Entity
public class Customer extends AuditedEntity {
}

@Entity
public class Product extends AuditedEntity {
}
```

`Customer` and `Product` are independent entity roots. This JPQL is invalid because `AuditedEntity` is not an entity:

```java
// Invalid JPQL
select a from AuditedEntity a
```

Use an **abstract entity root** when you need root queries or associations such as `@ManyToOne Payment payment`. Use `@MappedSuperclass` when you only want inherited fields/mappings. A subclass may override an inherited mapping with `@AttributeOverride` or `@AssociationOverride`.

### Selection guide

| Need | Usually start with |
|---|---|
| Frequent polymorphic reads; small, stable hierarchy | `SINGLE_TABLE` |
| Strong subtype constraints; normalized schema | `JOINED` |
| Mostly concrete-type reads; small hierarchy; verified provider support | `TABLE_PER_CLASS` |
| Field/mapping reuse without root queries or root associations | `@MappedSuperclass` |

#### Popularity: what the evidence supports

**There is no verified industry-wide winner between `SINGLE_TABLE` and `JOINED` in the evidence reviewed.** `SINGLE_TABLE` is the JPA default, which does not establish that it is the most used. Hibernate's 7.4 Short Guide describes `TABLE_PER_CLASS` as "not very popular"; this is a qualitative assessment, without adoption percentages.

#### Production examples, ranked by project popularity

The following open-source Java systems use Hibernate. Rank is by **GitHub stars retrieved on 2026-09-08**, among the verified examples below. Stars measure project interest, not installations or the frequency of a mapping strategy. Each example was checked in a released version for an actual mapped hierarchy and Hibernate integration; tutorials and provider tests were excluded. Source links pin the inspected revisions, and Hibernate versions vary by project.

| Rank | System and purpose | GitHub stars | Verified mapping | Concrete example and database shape |
|---|---|---:|---|---|
| 1 | Apollo 2.5.2 — configuration management | 29,802 | `@MappedSuperclass` | `BaseEntity` → `App`: shared ID and audit mappings become columns in `App`'s table; `BaseEntity` is not an entity root. |
| 2 | ThingsBoard 4.3.1.4 — Internet of Things platform | 22,383 | `@MappedSuperclass` | `AbstractDeviceEntity` → `DeviceEntity`: the device table receives inherited device fields without a parent-entity table. |
| 3 | Broadleaf Commerce 7.0.7-GA — e-commerce | 1,920 | `JOINED` | `OrderItemImpl` → `DiscreteOrderItemImpl`: a product line item uses a `BLC_ORDER_ITEM` row plus a `BLC_DISCRETE_ORDER_ITEM` row containing prices and the required product-variant reference (`SKU_ID`). |
| 4 | OpenMRS 2.7.6 — medical records | 1,909 | `JOINED` | `Order` → `DrugOrder`: common order data lives in `orders`; medication-specific data lives in `drug_order`, linked by `order_id`. This release declares the hierarchy with Hibernate XML `<joined-subclass>`. |
| 5 | OpenRemote 1.30.0 — Internet of Things platform | 1,894 | `SINGLE_TABLE` | `Asset` → `ThingAsset`: asset subtypes share `ASSET`; the `TYPE` discriminator selects the Java subtype. |
| 6 | Axelor Open Suite 9.1.7 — business management | 970 | `TABLE_PER_CLASS` | `BankStatementLine` → `BankStatementLineAFB120` / `BankStatementLineCAMT53`: statement-format subtypes have their own complete tables. Axelor's domain-model setting `strategy="CLASS"` generates `@Inheritance(strategy = InheritanceType.TABLE_PER_CLASS)`. |

Apollo also places `@Inheritance(TABLE_PER_CLASS)` on its non-entity `BaseEntity`; this does not turn the mapped superclass into a `TABLE_PER_CLASS` entity hierarchy. Inspect the entity root, not just a matching annotation.

Among the candidates verified in this research, use **OpenRemote** as the `SINGLE_TABLE` reference, **Broadleaf** as the highest-ranked `JOINED` reference, **Axelor** for `TABLE_PER_CLASS`, and **Apollo** for mapping reuse. These examples show how the strategies appear in real application domains; the ranking is not an exhaustive census of Java systems.

Before choosing:

1. Confirm the relationship is truly **is-a**; otherwise prefer composition or associations.
2. List the important queries: root-polymorphic or concrete-type?
3. Decide where subtype constraints must be enforced.
4. Inspect generated DDL and SQL against the production database.
5. Do not mix strategies inside one hierarchy in portable code; support for that combination is not required.

### Remember

> `SINGLE_TABLE` trades nullable columns for simple reads; `JOINED` trades joins for normalization; `TABLE_PER_CLASS` trades duplicated schema and unions for independent concrete tables; `@MappedSuperclass` provides mapping reuse without an entity hierarchy.

## Sources

- [Jakarta Persistence 3.2 specification — inheritance and mapping strategies](https://jakarta.ee/specifications/persistence/3.2/jakarta-persistence-spec-3.2#inheritance)
- [Jakarta Persistence 3.2 API — `InheritanceType`](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/inheritancetype)
- [Jakarta Persistence 3.2 API — `DiscriminatorColumn`](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/discriminatorcolumn)
- [Jakarta Persistence 3.2 API — `MappedSuperclass`](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/mappedsuperclass)
- [Hibernate ORM 7.4 User Guide — inheritance](https://docs.hibernate.org/orm/7.4/userguide/html_single/#entity-inheritance)
- [Hibernate ORM 7.4 Short Guide — strategy selection and qualitative popularity assessment](https://docs.hibernate.org/orm/7.4/introduction/html_single/#mapping-inheritance)
- Apollo 2.5.2: [mapped superclass](https://github.com/apolloconfig/apollo/blob/ed9785c87b390c22efece9ea7ec7eeab2d20a042/apollo-common/src/main/java/com/ctrip/framework/apollo/common/entity/BaseEntity.java#L39-L61), [App entity](https://github.com/apolloconfig/apollo/blob/ed9785c87b390c22efece9ea7ec7eeab2d20a042/apollo-common/src/main/java/com/ctrip/framework/apollo/common/entity/App.java#L31-L37), [Hibernate configuration](https://github.com/apolloconfig/apollo/blob/ed9785c87b390c22efece9ea7ec7eeab2d20a042/apollo-portal/src/main/resources/application.yml#L19-L24), [Hibernate metadata integration](https://github.com/apolloconfig/apollo/blob/ed9785c87b390c22efece9ea7ec7eeab2d20a042/apollo-common/src/main/java/com/ctrip/framework/apollo/common/jpa/SqlFunctionsMetadataBuilderContributor.java#L19-L32).
- ThingsBoard 4.3.1.4: [mapped superclass](https://github.com/thingsboard/thingsboard/blob/a488a4c138971c0264bf7fdc879871f68eead1e4/dao/src/main/java/org/thingsboard/server/dao/model/sql/AbstractDeviceEntity.java#L43-L56), [DeviceEntity](https://github.com/thingsboard/thingsboard/blob/a488a4c138971c0264bf7fdc879871f68eead1e4/dao/src/main/java/org/thingsboard/server/dao/model/sql/DeviceEntity.java#L27-L29), [Hibernate Session usage](https://github.com/thingsboard/thingsboard/blob/a488a4c138971c0264bf7fdc879871f68eead1e4/dao/src/main/java/org/thingsboard/server/dao/sql/JpaAbstractDao.java#L128-L132).
- Broadleaf Commerce 7.0.7-GA: [OrderItemImpl root](https://github.com/BroadleafCommerce/BroadleafCommerce/blob/179117fddfb05a9bb302dc63cda07291f4fed781/core/broadleaf-framework/src/main/java/org/broadleafcommerce/core/order/domain/OrderItemImpl.java#L94-L104), [DiscreteOrderItemImpl subtype](https://github.com/BroadleafCommerce/BroadleafCommerce/blob/179117fddfb05a9bb302dc63cda07291f4fed781/core/broadleaf-framework/src/main/java/org/broadleafcommerce/core/order/domain/DiscreteOrderItemImpl.java#L67-L89), [Hibernate configuration](https://github.com/BroadleafCommerce/BroadleafCommerce/blob/179117fddfb05a9bb302dc63cda07291f4fed781/common/src/main/java/org/broadleafcommerce/common/config/BroadleafCommonConfig.java#L59-L66).
- OpenMRS 2.7.6: [Order root mapping](https://github.com/openmrs/openmrs-core/blob/d8057a05f2796c8286bbba914350cce45793736c/api/src/main/resources/org/openmrs/api/db/hibernate/Order.hbm.xml#L19-L24), [DrugOrder joined-subclass mapping](https://github.com/openmrs/openmrs-core/blob/d8057a05f2796c8286bbba914350cce45793736c/api/src/main/resources/org/openmrs/api/db/hibernate/Order.hbm.xml#L103-L110), [mapping registration](https://github.com/openmrs/openmrs-core/blob/d8057a05f2796c8286bbba914350cce45793736c/api/src/main/resources/hibernate.cfg.xml#L66), [Hibernate session-factory configuration](https://github.com/openmrs/openmrs-core/blob/d8057a05f2796c8286bbba914350cce45793736c/api/src/main/resources/applicationContext-service.xml#L572-L575).
- OpenRemote 1.30.0: [Asset root and discriminator](https://github.com/openremote/openremote/blob/bf6ea01acd63552bfc9eaae07d44d10dd4000424/model/src/main/java/org/openremote/model/asset/Asset.java#L245-L248), [ThingAsset subtype](https://github.com/openremote/openremote/blob/bf6ea01acd63552bfc9eaae07d44d10dd4000424/model/src/main/java/org/openremote/model/asset/impl/ThingAsset.java#L25-L30), [Hibernate provider](https://github.com/openremote/openremote/blob/bf6ea01acd63552bfc9eaae07d44d10dd4000424/container/src/main/java/org/openremote/container/persistence/PersistenceService.java#L119-L121), [entity registration](https://github.com/openremote/openremote/blob/bf6ea01acd63552bfc9eaae07d44d10dd4000424/container/src/main/java/org/openremote/container/persistence/PersistenceService.java#L374-L408).
- Axelor Open Suite 9.1.7: [BankStatementLine root](https://github.com/axelor/axelor-open-suite/blob/d83c5402faf5abf801a9299e000e16441035ee36/axelor-bank-payment/src/main/resources/domains/BankStatementLine.xml#L8-L15), [AFB120 subtype](https://github.com/axelor/axelor-open-suite/blob/d83c5402faf5abf801a9299e000e16441035ee36/axelor-bank-payment/src/main/resources/domains/BankStatementLineAFB120.xml#L8-L13), [CAMT53 subtype](https://github.com/axelor/axelor-open-suite/blob/d83c5402faf5abf801a9299e000e16441035ee36/axelor-bank-payment/src/main/resources/domains/BankStatementLineCAMT53.xml#L8-L12), [Open Platform integration](https://github.com/axelor/axelor-open-suite/blob/d83c5402faf5abf801a9299e000e16441035ee36/README.md#L17).
- Axelor Open Platform 8.2.3: [generator translates CLASS to TABLE_PER_CLASS](https://github.com/axelor/axelor-open-platform/blob/1c4f31a16f876d2ce3e1a0bb26dc0e8f445eaebd/axelor-tools/src/main/java/com/axelor/tools/code/entity/model/Entity.java#L616-L624), [Hibernate dependency](https://github.com/axelor/axelor-open-platform/blob/1c4f31a16f876d2ce3e1a0bb26dc0e8f445eaebd/gradle/libs.gradle#L115-L120), [Hibernate JPA setup](https://github.com/axelor/axelor-open-platform/blob/1c4f31a16f876d2ce3e1a0bb26dc0e8f445eaebd/axelor-core/src/main/java/com/axelor/db/JpaModule.java#L29-L45).
- GitHub repository API — star-count snapshot retrieved 2026-09-08: [Apollo](https://api.github.com/repos/apolloconfig/apollo), [ThingsBoard](https://api.github.com/repos/thingsboard/thingsboard), [Broadleaf](https://api.github.com/repos/BroadleafCommerce/BroadleafCommerce), [OpenMRS](https://api.github.com/repos/openmrs/openmrs-core), [OpenRemote](https://api.github.com/repos/openremote/openremote), [Axelor Open Suite](https://api.github.com/repos/axelor/axelor-open-suite).
