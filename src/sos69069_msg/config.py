"""Global configuration for SOS69069 M3."""

CONTRACT_ADDRESS = "0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A"
EIP712_NAME = "69069"
EIP712_VERSION = "1"
CHAIN_ID = 1
MAX_METADATA_LENGTH = 64

DEFAULT_ETHERSCAN_KEY = "RU99NEJZV9F2EWS7A97RWVHDJN1ZQ29Q99"
DEFAULT_RPC = "https://ethereum-rpc.publicnode.com"
DEFAULT_MAX_FEE_GWEI = 50.0

# Board discovery metadata markers (users can publish these on-chain)
# Format: M3:<order number of the board address>  (M3:1 = first board, M3:2 = second, ...)
DEFAULT_DISCOVERY_CODES = ["M3:1"]
LEGACY_DISCOVERY_CODES = ["M/list"]   # old default; migrated to M3:1 on load

APP_TITLE = "SOS69069 M3"
APP_TAGLINE = "owned by no one"
APP_VERSION = "0.2.4"
