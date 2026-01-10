# Cache Invalidation Reference

This document lists all cache invalidation points in the application.

## Cache Invalidation Summary

Cache is automatically invalidated when data changes to ensure users always see current information.

## Card Operations

### Add Card to Controller
**Endpoint:** `/accesscontrol/controller/<id>/add_card` (POST)  
**Function:** [`add_card()`](door_control/doorctl/blueprints/doorctl.py:1464)  
**Invalidates:**
- `controller_<id>_cards_list` - Card list for this controller
- `controller_<id>_card_<num>` - Specific card details
- `global_cards_aggregated` - Global cards aggregated data

### Edit Card on Controller
**Endpoint:** `/accesscontrol/controller/<id>/card/<num>/edit` (POST)  
**Function:** [`edit_card_on_controller()`](door_control/doorctl/blueprints/doorctl.py:1361)  
**Invalidates:**
- `controller_<id>_card_<num>` - Specific card details
- `global_cards_aggregated` - Global cards aggregated data

### Delete Card from Controller
**Endpoint:** `/accesscontrol/controller/<id>/delete_card` (POST)  
**Function:** [`delete_card()`](door_control/doorctl/blueprints/doorctl.py:1591)  
**Invalidates:**
- `controller_<id>_cards_list` - Card list for this controller
- `controller_<id>_card_<num>` - Specific card details
- `global_cards_aggregated` - Global cards aggregated data

### Delete Card User
**Endpoint:** `/accesscontrol/controller/<id>/card/<num>/delete` (GET/POST)  
**Function:** [`delete_card_user()`](door_control/doorctl/blueprints/doorctl.py:1613)  
**Invalidates:**
- `controller_<id>_cards_list` - Card list for this controller
- `controller_<id>_card_<num>` - Specific card details
- `global_cards_aggregated` - Global cards aggregated data

### Deactivate Card
**Endpoint:** `/accesscontrol/controller/<id>/deactivate_card` (POST)  
**Function:** [`deactivate_card()`](door_control/doorctl/blueprints/doorctl.py:1635)  
**Invalidates:**
- `controller_<id>_card_<num>` - Specific card details
- `global_cards_aggregated` - Global cards aggregated data

## Global Card Operations

### Global Add Card
**Endpoint:** `/accesscontrol/global/cards/add` (POST)  
**Function:** [`global_add_card()`](door_control/doorctl/blueprints/doorctl.py:210)  
**Invalidates:**
- `controller_<id>_cards_list` - For each affected controller
- `controller_<id>_card_<num>` - For each affected controller
- `global_cards_aggregated` - Global cards aggregated data

### Global Delete Card from Controllers
**Endpoint:** `/accesscontrol/global/cards/delete-from-controllers` (POST)  
**Function:** [`global_delete_card_from_controllers()`](door_control/doorctl/blueprints/doorctl.py:314)  
**Invalidates:**
- `controller_<id>_cards_list` - For each affected controller
- `controller_<id>_card_<num>` - For each affected controller
- `global_cards_aggregated` - Global cards aggregated data

### Global Edit Card
**Endpoint:** `/accesscontrol/global/cards/edit/<id>` (POST)  
**Function:** [`globalcards_edit()`](door_control/doorctl/blueprints/doorctl.py:399)  
**Invalidates:**
- `controller_<id>_card_<num>` - For each affected controller
- `global_cards_aggregated` - Global cards aggregated data

## Time Profile Operations

### Add Time Profile
**Endpoint:** `/accesscontrol/controller/<id>/add_time_profile` (POST)  
**Function:** [`add_time_profile()`](door_control/doorctl/blueprints/doorctl.py:964)  
**Invalidates:**
- `controller_<id>_time_profiles` - For each selected controller

### Edit Time Profile
**Endpoint:** `/accesscontrol/controller/<id>/time_profile/<profile_id>/edit` (POST)  
**Function:** [`edit_time_profile()`](door_control/doorctl/blueprints/doorctl.py:1137)  
**Invalidates:**
- `controller_<id>_time_profiles` - For each selected controller

### Delete Time Profile
**Endpoint:** `/accesscontrol/controller/<id>/time_profile/<profile_id>/delete` (POST)  
**Function:** [`delete_time_profile()`](door_control/doorctl/blueprints/doorctl.py:1233)  
**Invalidates:**
- `controller_<id>_time_profiles` - For the affected controller

## Cache Keys Reference

### Global Cache Keys
- `controllers_list` - All controllers information
- `global_cards_aggregated` - Aggregated global cards data

### Per-Controller Cache Keys
- `controller_<id>_cards_list` - Card list for specific controller
- `controller_<id>_card_<num>` - Individual card details
- `controller_<id>_time_profiles` - Time profiles for controller
- `controller_<id>_door_states` - Door states (5 min TTL)

## Cache TTL (Time To Live)

- **Default:** 30 minutes (1800 seconds)
- **Door States:** 5 minutes (300 seconds) - for more current data
- **Configurable:** Set `CACHE_TTL` in `.env` file

## Manual Cache Management

### View Cache Statistics
**URL:** `/accesscontrol/cache/stats`  
**Function:** [`cache_stats()`](door_control/doorctl/blueprints/doorctl.py:2059)

Shows:
- Cache status (enabled/disabled)
- Hit rate and statistics
- Cache size and file count
- "Clear All Cache" button

### Clear All Cache
**URL:** `/accesscontrol/cache/clear` (POST)  
**Function:** [`clear_cache()`](door_control/doorctl/blueprints/doorctl.py:2065)

Removes all cache entries.

### Clear Specific Cache Key
**URL:** `/accesscontrol/cache/clear/<cache_key>` (POST)  
**Function:** [`clear_cache_key()`](door_control/doorctl/blueprints/doorctl.py:2076)

Removes a specific cache entry.

## Cache Warm-Up

### Splash Page Cache Warm-Up
**URL:** `/accesscontrol/` or `/accesscontrol`  
**Function:** [`accesscontrol()`](door_control/doorctl/blueprints/doorctl.py:617)

When you visit the splash page, it automatically warms up the cache in the background:
- Controllers list
- Global cards data
- Individual controller card lists

This ensures subsequent page loads are fast even on first visit.

## Logging

All cache operations are logged:

```
INFO: Cache HIT: controllers_list
DEBUG: Cache MISS: controller_425036451_cards_list
DEBUG: Cache SET: controller_425036451_cards_list, TTL: 1800s
INFO: Cache invalidated after adding card 12345 to controller 425036451
INFO: Starting cache warm-up
INFO: Cache warm-up completed
```

## Best Practices

1. **After bulk operations:** Clear cache manually at `/accesscontrol/cache/stats`
2. **Monitor hit rate:** Should be >70% after warm-up period
3. **Check logs:** Look for cache errors in application logs
4. **Adjust TTL:** If data changes frequently, reduce `CACHE_TTL` in `.env`
5. **Disable if needed:** Set `CACHE_ENABLED=false` in `.env` to disable caching

## Troubleshooting

### Cache Not Invalidating
- Check application logs for invalidation messages
- Verify cache files are being deleted in `/tmp/door_control_cache/`
- Ensure cache is enabled (`CACHE_ENABLED=true`)

### Stale Data Showing
- Clear cache manually at `/accesscontrol/cache/stats`
- Check if cache invalidation is working (check logs)
- Reduce `CACHE_TTL` for more frequent refreshes

### Cache Errors
- Check cache directory permissions
- Verify `/tmp/door_control_cache/` exists and is writable
- Check application logs for detailed error messages
