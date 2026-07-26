Our wallet used to lean on a third-party SD-JWT library, and now that data minimisation is
contractual I need `/app/broker` finished in-house. `mvn -f /app/broker/pom.xml package` has to
produce `/app/broker/target/sd-jwt-broker.jar`, run as

```
java -jar /app/broker/target/sd-jwt-broker.jar --config <cfg> --credentials <dir> --policy <file> --out <dir>
```

No third-party JOSE, JWT or crypto code may reach that jar or its classpath: JDK crypto and a JSON
parser only. The stored credentials carry the MicroProfile claim contract documented under
`/app/microprofile-jwt-auth/api`. The issuer's signing keys are not on this box: the config names
the key set the issuer publishes, and a run reads it from there.

`/app/broker/PRESENTATION_PROFILE.md` is the profile to implement: the acceptance ladder, how
disclosures resolve, how the smallest release satisfying the policy is picked, and the key binding
on the way out. Match it exactly. `<dir>/report.json` is checked byte for byte and every released
credential lands in `<dir>/presentations/<id>.sdjwt`.

`/app/broker/wallet.properties`, `/app/credentials` and `/app/broker/policy.json` are what we run
against today. A run only exits non-zero when that published key set cannot be read, and then it
writes nothing at all.
