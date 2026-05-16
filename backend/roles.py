from enum import Enum


class UserRole(str, Enum):
    """
    All user roles in the Fracttal PRM system.

    External (partner-side):
        partner_user    - registers deals, views pipeline, accesses assets/training
        partner_admin   - manages partner users, maintains partner profile

    Internal (Fracttal-side):
        channel_ops_admin - manages partner program, workflows, tiers, rule configuration
        channel_manager   - approves partners/deals, collaborates with partner
        sales_rep         - receives converted deals, updates pipeline
        sales_ops         - pricing rules, product catalog, quote approvals, reporting
        finance_approver  - discount/margin approvals
        system_admin      - user management, integration config, audit logs
    """
    partner_user = "partner_user"
    partner_admin = "partner_admin"
    channel_ops_admin = "channel_ops_admin"
    channel_manager = "channel_manager"
    sales_rep = "sales_rep"
    sales_ops = "sales_ops"
    finance_approver = "finance_approver"
    system_admin = "system_admin"


PARTNER_ROLES = {UserRole.partner_user, UserRole.partner_admin}

INTERNAL_ROLES = {
    UserRole.channel_ops_admin,
    UserRole.channel_manager,
    UserRole.sales_rep,
    UserRole.sales_ops,
    UserRole.finance_approver,
    UserRole.system_admin,
}
