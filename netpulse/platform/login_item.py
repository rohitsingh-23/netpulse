"""macOS ServiceManagement wrapper for Login Items.

Uses SMAppService (available on macOS 13.0+) to register the main application
as a login item natively without needing a helper application or launchd plist.
"""

import platform

try:
    import objc
    from ServiceManagement import SMAppService
    from ServiceManagement import SMAppServiceStatusNotFound
    from ServiceManagement import SMAppServiceStatusEnabled
    from ServiceManagement import SMAppServiceStatusRequiresApproval
    from Foundation import NSError
    _SERVICE_MANAGEMENT_AVAILABLE = True
except ImportError:
    _SERVICE_MANAGEMENT_AVAILABLE = False

from netpulse.utils.log import get_logger

logger = get_logger("login_item")

def _is_macos_13_or_newer() -> bool:
    """Check if we are on macOS 13 Ventura or newer."""
    try:
        mac_ver = platform.mac_ver()[0]
        major = int(mac_ver.split('.')[0])
        return major >= 13
    except Exception:
        return False

def set_login_item_enabled(enabled: bool) -> bool:
    """Enable or disable the application as a login item.

    Args:
        enabled: True to start at login, False otherwise.

    Returns:
        True if the operation succeeded, False otherwise.
    """
    if not _SERVICE_MANAGEMENT_AVAILABLE or not _is_macos_13_or_newer():
        logger.warning("SMAppService is not available (macOS 13+ required or PyObjC missing)")
        return False

    try:
        service = SMAppService.mainAppService()

        if enabled:
            if service.status() == SMAppServiceStatusEnabled:
                logger.info("Login item is already enabled.")
                return True

            success, error = service.registerAndReturnError_(None)
            if not success:
                logger.error("Failed to register login item: %s", error)
                return False

            logger.info("Successfully registered login item.")
            return True

        else:
            if service.status() == SMAppServiceStatusNotFound:
                logger.info("Login item is already unregistered.")
                return True

            success, error = service.unregisterAndReturnError_(None)
            if not success:
                logger.error("Failed to unregister login item: %s", error)
                return False

            logger.info("Successfully unregistered login item.")
            return True

    except Exception as e:
        logger.exception("Exception while configuring login item: %s", e)
        return False
