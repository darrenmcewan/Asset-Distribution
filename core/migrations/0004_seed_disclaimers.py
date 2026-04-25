from django.db import migrations


WELCOME_TITLE = "Welcome to the Family Asset Distribution Site"
WELCOME_BODY = """\
This site lets family members browse items from the estate and let everyone know which ones matter to you.

A few important things to keep in mind:

- **You are responsible for collecting any item you receive.** That includes arranging pickup or shipping at your own cost.
- Marking interest does **not** guarantee you will receive an item; the family will work through requests together.
- Be respectful in comments — they are visible to other family members.

Thank you for being part of this. Click the close button when you're ready to start.
"""

CLAIM_TITLE = "Before you claim this item"
CLAIM_BODY = """\
By confirming, you are letting the family know you would like this item.

Please remember:

- **You are responsible for arranging collection or shipping** of any item assigned to you, including any cost.
- Adding an item to your wishlist does not guarantee you will receive it.
- You can remove an item from your wishlist at any time before it is assigned.

Press **Confirm** to add this item to your wishlist, or **Cancel** to go back.
"""


def seed_disclaimers(apps, schema_editor):
    DisclaimerMessage = apps.get_model('core', 'DisclaimerMessage')
    DisclaimerMessage.objects.update_or_create(
        slug='welcome',
        defaults={'title': WELCOME_TITLE, 'body': WELCOME_BODY},
    )
    DisclaimerMessage.objects.update_or_create(
        slug='claim_confirmation',
        defaults={'title': CLAIM_TITLE, 'body': CLAIM_BODY},
    )


def remove_disclaimers(apps, schema_editor):
    DisclaimerMessage = apps.get_model('core', 'DisclaimerMessage')
    DisclaimerMessage.objects.filter(slug__in=['welcome', 'claim_confirmation']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_userprofile_welcome_disclaimer_dismissed_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_disclaimers, remove_disclaimers),
    ]
