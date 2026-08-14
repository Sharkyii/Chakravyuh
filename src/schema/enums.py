"""Closed-vocabulary fields from docs/data-schema-v1.md.

Only fields the schema doc gives an explicit `enum` type AND an explicit value
list become a Python Enum here. Fields the doc leaves as free-form (e.g.
`merchants.kyb_level`, `mandates.frequency`) are typed as `str` in the table
modules instead of an invented enum, so we never fabricate a value set the
doc didn't specify.
"""

from __future__ import annotations

from enum import Enum


class Rail(str, Enum):
    CARD_CNP = "card_cnp"
    CARD_CP = "card_cp"
    UPI_P2P = "upi_p2p"
    UPI_P2M = "upi_p2m"
    UPI_COLLECT_MERCHANT = "upi_collect_merchant"
    UPI_MANDATE = "upi_mandate"
    UPI_LITE = "upi_lite"
    IMPS = "imps"
    NEFT = "neft"
    WALLET = "wallet"
    BNPL = "bnpl"


class Channel(str, Enum):
    WEB = "web"
    APP = "app"
    POS = "pos"
    QR_STATIC = "qr_static"
    QR_DYNAMIC = "qr_dynamic"
    INTENT_LINK = "intent_link"
    AGENT = "agent"


class Direction(str, Enum):
    PUSH = "push"
    PULL = "pull"


class AuthMethod(str, Enum):
    NONE = "none"
    CVV_ONLY = "cvv_only"
    THREE_DS_FRICTIONLESS = "3ds_frictionless"
    THREE_DS_CHALLENGE_OTP = "3ds_challenge_otp"
    THREE_DS_CHALLENGE_BIOMETRIC = "3ds_challenge_biometric"
    UPI_PIN = "upi_pin"
    LITE_NONE = "lite_none"
    MANDATE_NO_AFA = "mandate_no_afa"


class AuthResult(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ABANDONED = "abandoned"
    NOT_ATTEMPTED = "not_attempted"


class ExemptionClaimed(str, Enum):
    NONE = "none"
    TRA = "tra"
    LOW_VALUE = "low_value"
    MIT = "mit"
    WHITELIST = "whitelist"
    DELEGATED = "delegated"


class Decision(str, Enum):
    APPROVED = "approved"
    DECLINED = "declined"
    FLAGGED_REVIEW = "flagged_review"


class PartyType(str, Enum):
    CONSUMER = "consumer"
    MERCHANT = "merchant"
    # Ground truth only — never a feature. See docs/data-schema-v1.md Table 2.
    MULE_UNKNOWN = "mule_unknown"


class KycLevel(str, Enum):
    FULL = "full"
    MIN_KYC = "min_kyc"
    VIDEO_KYC = "video_kyc"
    NONE = "none"


class VolumeGrowthCurve(str, Enum):
    ORGANIC = "organic"
    STEP = "step"
    SPIKE = "spike"


class EnrolledVia(str, Enum):
    APP = "app"
    WEB = "web"
    AGENT = "agent"
    LINK = "link"


class DetectableAt(str, Enum):
    PRE_AUTH = "pre_auth"
    POST_AUTH = "post_auth"
    POST_SETTLEMENT = "post_settlement"
    ONLY_IN_HINDSIGHT = "only_in_hindsight"


class DeviceType(str, Enum):
    """Not in docs/data-schema-v1.md — part of the `devices` table added to
    support transactions.device_id (fk -> devices) and the device population
    generator described in the master brief. See src/schema/devices.py.
    """

    ANDROID = "android"
    IOS = "ios"
    DESKTOP = "desktop"
    POS_TERMINAL = "pos_terminal"
    OTHER = "other"
