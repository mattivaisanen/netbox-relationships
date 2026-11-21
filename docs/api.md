# REST API

Everything is under `/api/plugins/relationships/` and uses NetBox API
tokens and permissions.

## Models

| Endpoint | Model |
|---|---|
| `relationship-types/` | Relationship types |
| `relationships/` | Relationships |
| `logical-services/` | Logical services |
| `network-tiers/` | Network tiers (`name`, `slug`, `level`, `roles` as device role IDs) |

These support the usual list, get, create, update, delete, bulk operations
and filters. Relationships filter by `type` (slug), `type_id`, `status`,
`category`, `criticality`, `source_type` (`dcim.device`), `source_id`, `target_type`,
`target_id`, and `object`, which matches either end (`?object=dcim.device:7`).

Relationships also have `impact` (`hard`, `soft`, `none`, or empty for the
type's default), `label`, `group` and `group_min` (see
[usage](usage.md#redundancy)).

Create a relationship:

```http
POST /api/plugins/relationships/relationships/
{
  "type": 1,
  "source_type": "virtualization.virtualmachine", "source_id": 12,
  "target_type": "dcim.device", "target_id": 7,
  "criticality": "high", "impact": "soft", "label": "Nightly export"
}
```

## Object references

The graph and impact endpoints name objects as `<type>:<id>`, with the type
either as `app.model` (`dcim.device:7`) or as a content type ID (`12:7`).

## Graph

```http
GET /api/plugins/relationships/graph/?object=dcim.device:7&depth=3&direction=both
```

| Parameter | Meaning |
|---|---|
| `object` | Start object. Repeat for several. |
| `depth` | Hops, up to `max_depth`. |
| `direction` | `down` (what it needs), `up` (what needs it) or `both`. |
| `derived` | `false` to leave out links read from NetBox. |
| `status` | Only relationships with this status. Repeatable. |
| `type` | Only relationships of this type ID. Repeatable. |

The answer has `nodes`, `edges`, `roots` and `truncated`. Each node has
`id`, `label`, `kind`, `group`, `url`, `status`, `hops`, `root` and
`hidden`. Each edge has `source`, `target`, `label`, `origin` (`manual` or
`netbox`), `kind` (the origin key, such as `cables`), `impact`,
`symmetric`, `status`, `criticality`, `group`, `group_min`, `link_count`
and `note`.

## Impact

```http
POST /api/plugins/relationships/impact/
{"objects": ["dcim.device:7"], "include_planned": false}
```

The answer has `failed`, `affected` (each with `state`: `down`,
`degraded` or `at_risk`, `hops` and `chain`), a `summary` (counts,
business services, owners, tenants), `truncated`, and `links`: for each
failed object that affected nothing, how many links it has and how many
carry impact.
