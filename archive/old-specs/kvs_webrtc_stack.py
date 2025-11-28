"""
Amazon Kinesis Video Streams WebRTC Stack
Provides WebRTC signaling channels and STUN/TURN infrastructure for low-latency audio streaming
"""
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_logs as logs,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


class KVSWebRTCStack(Stack):
    """
    CDK Stack for Kinesis Video Streams WebRTC infrastructure.
    
    Note: KVS Signaling Channels are created dynamically per session via Lambda,
    not pre-created in CDK. This stack sets up IAM roles and permissions.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cognito_identity_pool_id: str = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ========================================
        # IAM Role for Lambda to Manage KVS Channels
        # ========================================
        
        self.kvs_management_role = iam.Role(
            self,
            'KVSManagementRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            description='Lambda role for managing KVS signaling channels',
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    'service-role/AWSLambdaBasicExecutionRole'
                ),
            ],
        )

        # Grant KVS signaling channel management permissions
        self.kvs_management_role.add_to_policy(
            iam.PolicyStatement(
                sid='KVSSignalingChannelManagement',
                actions=[
                    'kinesisvideo:CreateSignalingChannel',
                    'kinesisvideo:DeleteSignalingChannel',
                    'kinesisvideo:DescribeSignalingChannel',
                    'kinesisvideo:GetSignalingChannelEndpoint',
                    'kinesisvideo:UpdateSignalingChannel',
                    'kinesisvideo:ListSignalingChannels',
                    'kinesisvideo:TagResource',
                    'kinesisvideo:UntagResource',
                    'kinesisvideo:ListTagsForResource',
                ],
                resources=[
                    f'arn:aws:kinesisvideo:{self.region}:{self.account}:channel/session-*/*'
                ],
            )
        )

        # Grant ICE server configuration permissions
        self.kvs_management_role.add_to_policy(
            iam.PolicyStatement(
                sid='KVSIceServerConfig',
                actions=[
                    'kinesisvideo:GetIceServerConfig',
                ],
                resources=[
                    f'arn:aws:kinesisvideo:{self.region}:{self.account}:channel/session-*/*'
                ],
            )
        )

        # ========================================
        # IAM Role for Frontend Clients (via Cognito Identity Pool)
        # ========================================
        
        if cognito_identity_pool_id:
            # Authenticated users role (speakers)
            self.kvs_client_role = iam.Role(
                self,
                'KVSClientRole',
                assumed_by=iam.FederatedPrincipal(
                    'cognito-identity.amazonaws.com',
                    conditions={
                        'StringEquals': {
                            'cognito-identity.amazonaws.com:aud': cognito_identity_pool_id
                        },
                        'ForAnyValue:StringLike': {
                            'cognito-identity.amazonaws.com:amr': 'authenticated'
                        },
                    },
                    assume_role_action='sts:AssumeRoleWithWebIdentity',
                ),
                description='Frontend client role for KVS WebRTC access (authenticated/speakers)',
            )

            # Grant client permissions for WebRTC signaling
            self.kvs_client_role.add_to_policy(
                iam.PolicyStatement(
                    sid='KVSWebRTCSignaling',
                    actions=[
                        'kinesisvideo:ConnectAsMaster',
                        'kinesisvideo:ConnectAsViewer',
                        'kinesisvideo:DescribeSignalingChannel',
                        'kinesisvideo:GetSignalingChannelEndpoint',
                        'kinesisvideo:GetIceServerConfig',
                        'kinesisvideo:SendAlexaOfferToMaster',
                    ],
                    resources=[
                        f'arn:aws:kinesisvideo:{self.region}:{self.account}:channel/session-*/*'
                    ],
                )
            )
            
            # Unauthenticated users role (listeners/guests)
            self.kvs_guest_role = iam.Role(
                self,
                'KVSGuestRole',
                assumed_by=iam.FederatedPrincipal(
                    'cognito-identity.amazonaws.com',
                    conditions={
                        'StringEquals': {
                            'cognito-identity.amazonaws.com:aud': cognito_identity_pool_id
                        },
                        'ForAnyValue:StringLike': {
                            'cognito-identity.amazonaws.com:amr': 'unauthenticated'
                        },
                    },
                    assume_role_action='sts:AssumeRoleWithWebIdentity',
                ),
                description='Guest/listener role for KVS WebRTC access (unauthenticated)',
            )

            # Grant guest permissions for WebRTC signaling (viewer-only)
            # Listeners can only connect as viewers, not as masters
            self.kvs_guest_role.add_to_policy(
                iam.PolicyStatement(
                    sid='KVSWebRTCViewerAccess',
                    actions=[
                        'kinesisvideo:ConnectAsViewer',
                        'kinesisvideo:DescribeSignalingChannel',
                        'kinesisvideo:GetSignalingChannelEndpoint',
                        'kinesisvideo:GetIceServerConfig',
                    ],
                    resources=[
                        f'arn:aws:kinesisvideo:{self.region}:{self.account}:channel/session-*/*'
                    ],
                )
            )

        # ========================================
        # CloudWatch Log Groups for KVS Monitoring
        # ========================================
        
        self.kvs_log_group = logs.LogGroup(
            self,
            'KVSLogGroup',
            log_group_name='/aws/kinesisvideo/webrtc',
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ========================================
        # Outputs
        # ========================================
        
        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            'KVSManagementRoleArn',
            value=self.kvs_management_role.role_arn,
            description='IAM Role ARN for Lambda KVS management',
            export_name=f'{construct_id}-ManagementRoleArn',
        )

        if cognito_identity_pool_id:
            CfnOutput(
                self,
                'KVSClientRoleArn',
                value=self.kvs_client_role.role_arn,
                description='IAM Role ARN for frontend KVS clients (authenticated)',
                export_name=f'{construct_id}-ClientRoleArn',
            )
            
            CfnOutput(
                self,
                'KVSGuestRoleArn',
                value=self.kvs_guest_role.role_arn,
                description='IAM Role ARN for frontend KVS guests (unauthenticated/listeners)',
                export_name=f'{construct_id}-GuestRoleArn',
            )
