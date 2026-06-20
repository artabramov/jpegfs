class JpegFsError(Exception):
    pass


class ContainerExistsError(JpegFsError):
    pass


class ContainerNotFoundError(JpegFsError):
    pass


class InvalidPasswordError(JpegFsError):
    pass


class InsufficientShardsError(JpegFsError):
    pass


class NoCarriersError(JpegFsError):
    pass


class NotEnoughCarriersError(JpegFsError):
    pass


class ContainerFileExistsError(JpegFsError):
    pass


class ContainerFileNotFoundError(JpegFsError):
    pass
