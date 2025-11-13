# Repairs Feature Implementation

## Overview

Added Home Assistant Repairs framework support to the SFPUC integration. This allows users to be automatically notified when their credentials expire or become invalid, with an easy way to fix the issue.

## Features Implemented

### 1. Automatic Issue Detection

- **Credential Validation**: Monitors login attempts during data updates
- **Error Detection**: Automatically detects authentication failures
- **Repair Creation**: Creates a "repair issue" when credentials fail
- **User Notification**: Displays notification in Home Assistant UI

### 2. Self-Healing Repairs Flow

- **Step 1 - Initial**: Shows the user the issue and asks if they want to fix it
- **Step 2 - Confirmation**: Presents a form to enter updated credentials
- **Automatic Reload**: Tests new credentials and reloads the integration if valid

### 3. Multilingual Support

- **English**: "Invalid SFPUC Credentials" repair issue
- **Spanish**: "Credenciales SFPUC Inválidas" repair issue
- Both include description of why credentials might be invalid

## Files Modified/Created

### New Files:

1. **`repairs.py`** - Repairs framework implementation

   - `async_check_issues()`: Periodic check for issues
   - `SFWaterCredentialsRepair`: Repair flow handler
   - `async_create_fix_flow()`: Flow factory function

2. **`tests/test_repairs.py`** - Test suite for repairs
   - 3 test cases covering repair flow steps

### Modified Files:

1. **`__init__.py`**

   - Added `async_setup()` to register repairs flow
   - Added error handling in `async_setup_entry()` to create issues on startup failure
   - Error detection for credential issues

2. **`coordinator.py`**

   - Added repair creation on authentication failure
   - Improved error messages for credential issues

3. **`strings.json`** - English translations

   - Added repair issue title and description

4. **`translations/es.json`** - Spanish translations
   - Added Spanish repair issue title and description

## How It Works

### User Experience

1. **Issue Triggered**: When credentials become invalid, the integration fails to log in
2. **Notification**: Home Assistant shows a notification in the UI
3. **Repair Card**: User sees a "San Francisco Water Power Sewer" repair card
4. **Fix Flow**: User clicks to start the repair process
5. **Update Form**: User enters updated username/password
6. **Auto Test**: Integration tests credentials and reloads if valid

### Developer View

```
Login Failure
    ↓
coordinator.py creates repair issue
    ↓
__init__.py handles in error path
    ↓
repairs.py flow handles user interaction
    ↓
Config entry updated and reloaded
    ↓
Integration resumes normal operation
```

## Issue Types Currently Supported

### `invalid_credentials`

- **Severity**: Error
- **Fixable**: Yes (user can re-enter credentials)
- **Triggers**:
  - Login fails during coordinator update
  - Invalid username/password
  - Account locked
  - Permission changes

## Translation Keys

### Repair Issue Translations

Translation strings are stored in the `issues` section (not `repairs`) of strings.json:

**English (strings.json):**

```json
{
  "issues": {
    "invalid_credentials": {
      "title": "Invalid SFPUC Credentials",
      "description": "The credentials for account '{account}' are no longer valid. This could be due to:\n\n• Password has been changed\n• SFPUC account locked\n• Account permissions changed\n\nClick below to update your credentials."
    }
  }
}
```

**Spanish (translations/es.json):**

```json
{
  "issues": {
    "invalid_credentials": {
      "title": "Credenciales SFPUC Inválidas",
      "description": "Las credenciales para la cuenta '{account}' ya no son válidas. Esto podría deberse a:\n\n• La contraseña ha sido cambiada\n• Cuenta SFPUC bloqueada\n• Los permisos de la cuenta han sido cambiados\n\nHaga clic a continuación para actualizar sus credenciales."
    }
  }
}
```

**Note**: The `{account}` placeholder is replaced at runtime with the actual account username.

## Testing

All tests pass:

- ✅ 75 total tests passing
- ✅ 3 new repair tests
- ✅ All existing tests still pass
- ✅ No regressions

### Test Coverage

- Repair flow initialization
- Repair flow confirmation step
- Config entry update with new credentials
- Integration reload after credential update

## Future Enhancements

Potential additions:

1. **Rate Limiting**: Prevent too many failed attempts
2. **Email Notifications**: Optional email alerts
3. **Network Issues**: Separate repair for connectivity problems
4. **Account Locked**: Specific repair for account lockout
5. **Data Gaps**: Notification when data fetch fails repeatedly

## User Guide

### When to expect a repair notification:

- Password has been changed on SFPUC account
- Account has been locked due to login attempts
- Account permissions have been revoked
- SFPUC made changes to your account

### How to fix:

1. Look for the notification in Home Assistant
2. Click "San Francisco Water Power Sewer" repair
3. Click the fix option
4. Enter your updated SFPUC username and password
5. Integration will test and reload automatically

### If it still doesn't work:

- Check your SFPUC account at https://myaccount-water.sfpuc.org
- Verify you can login manually
- Check logs for more detailed error messages
- Report issue on GitHub if problem persists
