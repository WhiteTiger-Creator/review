Signing-key reuse is based on key material identity, not on `kid` alone.

For `token_issued` events, the event payload field is `material_id`. For keyset configuration entries, the corresponding private material field is `private_material_id`. These names are intentionally different because event payloads describe observed token issuance while keysets describe configured signing material.

A `signing_key_reuse` finding is emitted when two token-issued events resolve to the same key material identity but different issuers. For the bundled event payloads, compare nonempty `payload.material_id` values. Do not compare only `kid`, and do not require the event payload to contain `private_material_id`.
