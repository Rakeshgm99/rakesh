import libtaxii as t
import libtaxii.clients as tc
import libtaxii.messages_11 as tm11
from libtaxii.constants import *

from datetime import datetime, timedelta
from dateutil.tz import tzutc
import xmltodict
from .rf_notes_to_stix2 import IPAddress
import stix2
from pycti import Identity



class TaxiiUtils:
    def __init__(self):
        self.author = stix2.Identity(
            id=Identity.generate_id("Recorded Future", "organization"),
            name="Recorded Future",
            identity_class="organization",
        )

    def run(self):
        client = self.config_server()

        taxii_message = self.query(client)

        bundle = self.extract_data(taxii_message)
        stix2.Bundle(objects=bundle, allow_custom=True)

    def extract_data(self, taxii_message):
        all_indicators = []
        for block in taxii_message.content_blocks:
            my_dict = xmltodict.parse(block.content)
            all_indicators.extend(
                my_dict["stix:STIX_Package"]["stix:Indicators"]["stix:Indicator"]
            )
        print("1")
        bundle = []
        for indicator in all_indicators:
            RF_indicator = self.extract_indicator_from_taxii_indicator(indicator)
            bundle.extend(RF_indicator.to_stix_objects())
        return bundle

    def query(self, client):
        # discovery_request = tm11.DiscoveryRequest(tm11.generate_message_id())
        # discovery_xml = discovery_request.to_xml()
        # TODO Check possibility to paginate
        # query = tm11.Query()
        poll_params = tm11.PollParameters(
            allow_asynch=True,
            response_type=RT_COUNT_ONLY,
            content_bindings=[tm11.ContentBinding(binding_id=CB_STIX_XML_11)],
            # query=query
        )
        begin = datetime.now(tzutc()) + timedelta(days=-1)
        end = datetime.now(tzutc())
        poll_request = tm11.PollRequest(
            tm11.generate_message_id(),
            collection_name="domain_full",
            poll_parameters=poll_params,
            inclusive_end_timestamp_label=end,
            exclusive_begin_timestamp_label=begin,
        )
        poll_request_xml = poll_request.to_xml()
        # http_resp = client.call_taxii_service2('api.recordedfuture.com/taxii', '/pollservice/', VID_TAXII_XML_11, discovery_xml)
        http_resp = client.call_taxii_service2(
            "api.recordedfuture.com",
            "/taxii/pollservice/",
            VID_TAXII_XML_11,
            poll_request_xml,
        )
        taxii_message = t.get_message_from_http_response(
            http_resp, poll_request.message_id
        )
        return taxii_message

    def config_server(self):
        client = tc.HttpClient()
        client.set_auth_type(tc.HttpClient.AUTH_BASIC)
        client.set_use_https(True)
        client.set_auth_credentials(
            {"username": "MyUsername", "password": "17aca155572d42cab8fd7b525d093d6c"}
        )
        return client

    def extract_indicator_from_taxii_indicator(self, taxii_indicator) -> IPAddress:
        type = taxii_indicator["indicator:Observable"]["cybox:Object"][
            "cybox:Properties"
        ]["@category"]
        value = taxii_indicator["indicator:Observable"]["cybox:Object"][
            "cybox:Properties"
        ]["AddressObj:Address_Value"]["#text"]
        # if no value in the first field, we get it from the Title
        # Title is like 'IP Address 5.42.65.101'
        if value is None:
            # TODO change this algo as it won't work for ip addresses
            space_index = taxii_indicator["indicator:Title"].find(" ")
            value = taxii_indicator["indicator:Title"][
                space_index + 1 :
            ]  # take the text after the space, which is the indicator
        return IPAddress(value, type, self.author)
