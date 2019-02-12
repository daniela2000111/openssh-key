import base64
import io

import struct

from openssh_key.openssh_io import read_openssh_string, unarmor_ascii_openssh_key
from openssh_key.private_keys import read_private_key_data

AUTH_MAGIC = b"openssh-key-v1\0"


class Keypair:
    public_key: bytes = None  # The public key
    key_format: bytes = None  # The key format
    private_key: bytes = None  # The private key in a private serialization format dependent on key_format
    comment: bytes = None  # The comment

    @property
    def public_key_string(self):
        return '%s %s %s' % (
            self.key_format.decode(),
            base64.b64encode(self.public_key).decode(),
            self.comment.decode('UTF-8'),
        )


class OpenSSHKeyInfo:
    cipher_name: bytes = None
    kdf_name: bytes = None
    kdf_options: bytes = None
    num_keys: int = None
    public_keys: list = None
    encrypted_private_keys: bytes = None

    @classmethod
    def parse_binary(cls, binary_data):
        """
        Parse the binary data for an openssh key structure.

        The format is described in
        https://github.com/openssh/openssh-portable/blob/5c68ea8da790d711e6dd5f4c30d089c54032c59a/PROTOCOL.key
        """

        bio = io.BytesIO(binary_data)
        header = bio.read(len(AUTH_MAGIC))
        if header != AUTH_MAGIC:
            raise ValueError('data began with %r, not %r' % (header, AUTH_MAGIC))
        ki = cls()
        ki.cipher_name = read_openssh_string(bio)
        ki.kdf_name = read_openssh_string(bio)
        ki.kdf_options = read_openssh_string(bio)
        ki.num_keys, = struct.unpack('!I', bio.read(4))
        ki.public_keys = [read_openssh_string(bio) for x in range(ki.num_keys)]
        ki.encrypted_private_keys = read_openssh_string(bio)
        leftover = bio.read()
        if leftover:
            raise ValueError('not all data was read (left over: %r)' % leftover)
        return ki

    @classmethod
    def parse_text(cls, text_fp):
        return cls.parse_binary(unarmor_ascii_openssh_key(text_fp))

    def decrypt_keypairs(self, passphrase=None):
        if self.cipher_name == b'none':
            decrypted_private_keys = self.encrypted_private_keys
        else:
            # TODO: support ciphers and populate decrypted_private_key here
            raise NotImplementedError('The %r cipher is not yet supported' % self.cipher_name)

        bio = io.BytesIO(decrypted_private_keys)
        checkint1, checkint2 = struct.unpack('!II', bio.read(8))
        if checkint1 != checkint2:
            raise ValueError('checkint mismatch: %08x != %08x' % (checkint1, checkint2))
        for public_key in self.public_keys:
            kp = Keypair()
            kp.public_key = public_key
            kp.key_format, kp.private_key = read_private_key_data(bio)
            kp.comment = read_openssh_string(bio)
            yield kp
