"""

Create an AWS VPC.

Python Version: 3.8.0
Boto3 Version: 1.15.2


"""
import boto3
from botocore.exceptions import ClientError
from netaddr import *
from pathlib import Path
import jsonschema
import json
import logging


class Tag():
    """
    create Tags
    """

    def __init__(self, name, resource):

        self.name = name.lower() + '-' + resource

    def resource(self, ec2, resource_id):

        try:
            ec2.create_tags(
                Resources=[
                    resource_id
                ],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': self.name
                    }
                ]
            )
        except ClientError as e:
            return e.response['Error']['Message']


def create_vpc_aws(ec2, cidr, name):
    """
  Create a VPC
  """

    args = {
        'CidrBlock': cidr,
        'InstanceTenancy': 'default'
    }

    try:
        vpc = ec2.create_vpc(**args)['Vpc']
    except ClientError as e:
        print(e.response['Error']['Message'])
        return None

    vpc_id = vpc['VpcId']

    try:
        ec2.modify_vpc_attribute(
            EnableDnsSupport={
                'Value': True
            },
            VpcId=vpc_id
        )

        ec2.modify_vpc_attribute(
            EnableDnsHostnames={
                'Value': True
            },
            VpcId=vpc_id
        )
    except ClientError as e:
        return e.response['Error']['Message']

    tag = Tag(name, 'vpc')
    tag.resource(ec2, vpc_id)
    print('vpc_id: {}'.format(vpc_id))

    return vpc_id


def create_igw(ec2, vpc_id, name):
    """
  Create and attach an internet gateway
  """

    try:
        igw = ec2.create_internet_gateway()['InternetGateway']
    except ClientError as e:
        print(e.response['Error']['Message'])
        return None

    igw_id = igw['InternetGatewayId']

    try:
        ec2.attach_internet_gateway(
            InternetGatewayId=igw_id,
            VpcId=vpc_id
        )
    except ClientError as e:
        return e.response['Error']['Message']

    tag = Tag(name, 'igw')
    tag.resource(ec2, igw_id)
    print('igw_id: {}'.format(igw_id))

    return igw_id


def subnet_sizes(cidr):
    """
  Calculate subnets sizes
  """

    global subnets
    netmasks = (
        '255.255.255.0',
        '255.255.254.0',
        '255.255.252.0',
        '255.255.248.0',
        '255.255.240.0',
        '255.255.224.0',
        '255.255.192.0',
        '255.255.128.0',
        '255.255.0.0'
    )

    ip = IPNetwork(cidr)
    mask = ip.netmask

    if str(mask) not in netmasks:
        logging.critical('Netmask not allowed: {}'.format(mask))
        return None

    for n, netmask in enumerate(netmasks):
        if str(mask) == netmask:
            subnets = list(ip.subnet(26 - n))

    return subnets


def create_sub(ec2, vpc_id, subnets, zones, name):
    """
  Create subnets
  """

    i = 0
    subnet_ids = []
    tier = 'public'

    for subnet in subnets:

        args = {
            'AvailabilityZone': zones[i],
            'CidrBlock': str(subnet),
            'VpcId': vpc_id
        }

        try:
            sub = ec2.create_subnet(**args)['Subnet']
        except ClientError as e:
            logging.critical(e.response['Error']['Message'])
            return None

        subnet_id = sub['SubnetId']
        subnet_ids.append(subnet_id)

        tag = Tag(name, 'sub' + '-' + tier)
        tag.resource(ec2, subnet_id)
        print('sub_id: {} size: {} zone: {} tier: {}'.format(subnet_id, subnet, zones[i], tier))

        i += 1

        if i == 2:
            i = 0
            tier = 'private'

    return subnet_ids


def create_rtb(ec2, vpc_id, subnet_ids, igw_id, name):
    """
  Create and associate route tables
  """

    global rtb_id
    i = 0
    route_table_ids = []
    tier = 'public'

    for subnet in subnet_ids:
        if i == 0:

            try:
                rtb = ec2.create_route_table(VpcId=vpc_id)['RouteTable']
            except ClientError as e:
                return e.response['Error']['Message']

            rtb_id = rtb['RouteTableId']
            route_table_ids.append(rtb_id)

            if tier == 'public' and igw_id != None:
                try:
                    result = ec2.create_route(
                        DestinationCidrBlock='0.0.0.0/0',
                        GatewayId=igw_id,
                        RouteTableId=rtb_id
                    )
                except ClientError as e:
                    return e.response['Error']['Message']

            tag = Tag(name, 'rtb' + '-' + tier)
            tag.resource(ec2, rtb_id)
            print('rtb_id: {} tier: {}'.format(rtb_id, tier))

        try:
            ec2.associate_route_table(
                RouteTableId=rtb_id,
                SubnetId=subnet
            )
        except ClientError as e:
            return e.response['Error']['Message']

        i += 1

        if i == 2:
            i = 0
            tier = 'private'

    return route_table_ids


def get_zones(ec2):
    """
  Return all available zones in the region
  """

    zones = []

    try:
        aws_zones = ec2.describe_availability_zones()['AvailabilityZones']
    except ClientError as e:
        print(e.response['Error']['Message'])
        return None

    for zone in aws_zones:
        if zone['State'] == 'available':
            zones.append(zone['ZoneName'])

    return zones


def main(requests):
    """

  Order of operation:

  1.) Create the VPC
  2.) Create and attach an internet gateway
  3.) Calculate subnet sizes (netaddr)
  4.) Create the subnets
  5.) Create and associate route tables

  """

    try:

        ec2 = boto3.client('ec2', region_name=requests["region"])

        zones = get_zones(ec2)
        if zones is None or len(zones) < 2:
            return

        subnets = subnet_sizes(cidr=requests["cidr"])
        if subnets is None:
            return

        vpc_id = create_vpc_aws(ec2, cidr=requests["cidr"], name=requests['name'])
        if vpc_id is None:
            return

        igw_id = create_igw(ec2, vpc_id, name=requests['name'])
        sub_ids = create_sub(ec2, vpc_id, subnets, zones, name=requests['name'])
        if sub_ids is None:
            return

        rtb_id = create_rtb(ec2, vpc_id, sub_ids, igw_id, name=requests['name'])

        return {"Message": "Successful Response", "vpc": {"vpcId": [vpc_id], "InternetGatewayId": [igw_id],
                                                          "routeTableId": [rtb_id], "subnet": [sub_ids]}}

    except ClientError as e:
        logging.critical("It is ClientError")
        logging.critical(e.response)
        return {"Message": "Unsuccessful response", "Error": [e.response["Error"]]}
    except KeyError as e:
        logging.critical("It is KeyError")
        return {"Message": "Unsuccessful response", "Error": [e.args[0]]}


def validate_input_json(json_schema, json_data):
    """
        Validate the schema of the input JSON
        Args:
            req_json:  JSON object with vm information
        Returns:
            Result message
            :param json_data:
            :param json_schema:
    """
    data = json_data
    base_path = Path(__file__).parent
    file_path = (base_path / f"../data/{json_schema}").resolve()
    with open(file_path, 'r') as f:
        schema_data = f.read()
    schema = json.loads(schema_data)
    try:
        jsonschema.validate(data, schema)
        logging.info('JSON Schema validation was successful')
        return "Successful"

    except jsonschema.ValidationError as e:
        logging.critical(f'JSON validation failed due to: {e.message}')
        raise jsonschema.ValidationError(e.message)
