"""Custom exceptions for pdfcat."""


class PdfcatError(Exception):
    """Base exception for pdfcat errors."""


class DocumentError(PdfcatError):
    """Document-related errors."""


class RenderError(PdfcatError):
    """Rendering-related errors."""


class ConfigError(PdfcatError):
    """Configuration-related errors."""


class SecurityError(PdfcatError):
    """Security validation errors."""


class NoteError(PdfcatError):
    """Note-taking errors."""


class NeovimBridgeError(PdfcatError):
    """Neovim integration errors."""
