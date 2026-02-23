import json
from datetime import datetime, timedelta
from functools import partialmethod

import jwt


class ServerSigner:
    ASPECT_KEY = "authorization"
    ONE_HOUR = 3600

    def __init__(self, app_def_id: str, app_secret: str):
        """
        Creates a JWT signature for GRPC calls within the Wix ecosystem.
        :param app_def_id: Wix TPA App ID
        :param app_secret: Wix TPA App Secret Key
        """
        self.app_def_id = app_def_id
        self.app_secret = app_secret

    def sign_attribute(self, attribute_key, attribute_value):
        d = {attribute_key: attribute_value}
        return self._sign_generic(d)

    def _sign_generic(self, attribute_dict):
        payload_data = {"appDefId": self.app_def_id, **attribute_dict}
        payload = {"data": json.dumps(payload_data)}
        return self._generate_authorization(payload)

    sign_app = partialmethod(_sign_generic, {})
    sign_meta_site = partialmethod(sign_attribute, "metaSiteId")
    sign_instance = partialmethod(sign_attribute, "instanceId")
    sign_account = partialmethod(sign_attribute, "accountId")

    def _generate_authorization(self, data_to_sign):
        payload = self._generate_payload(data_to_sign)
        signature = 'SRV.JWS.' + jwt.encode(payload, self.app_secret)
        return {self.ASPECT_KEY: signature.encode("utf-8")}

    def _generate_payload(self, payload):
        current_timestamp = datetime.now()
        attributes_to_add = {
            "exp": int((current_timestamp + timedelta(seconds=self.ONE_HOUR)).timestamp()),
            "iat": int(current_timestamp.timestamp()),
        }
        payload.update(attributes_to_add)
        return payload

    def decode_jwt(self, signature: bytes) -> dict:
        return jwt.decode(
            signature.replace(b'SRV.JWS.', b''),
            self.app_secret,
            algorithms='HS256',
        )

    def decode_app_def_id(self, signature: bytes) -> str:
        data = self.decode_jwt(signature)['data']
        return json.loads(data)['appDefId']
