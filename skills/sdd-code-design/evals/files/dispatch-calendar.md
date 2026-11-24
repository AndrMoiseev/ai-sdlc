# Billing delivery review

The review template has two lines.

1. Production billing code must never call `ZoneId.systemDefault()`.
2. On a replay, the billing date printed on a notice belongs to the statement instant and the account's billing zone.

Both lines are currently signed off by a reviewer. A release engineer wants to retire both now that the following build rule is required. The compiler plugin resolves symbols in every production billing module, including generated production sources. It rejects every reference to `java.time.ZoneId.systemDefault`. Its complete deny set contains that one symbol. A seeded direct call in a rarely used billing module did fail CI.

```kotlin
data class Replay(val statementAt: Instant, val account: Account)
fun noticeDate(at: Instant, zone: ZoneId): LocalDate = at.atZone(zone).toLocalDate()

val date = noticeDate(replay.statementAt, replay.account.billingZone)
```

The platform also supplies a worker clock, a tenant's default zone and UTC. All are legitimate elsewhere. No new build rules are available this release. The original checklist must fit on one line after this review.
