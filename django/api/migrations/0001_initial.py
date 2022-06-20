# Generated by Django 4.0.1 on 2022-06-17 20:16

import api.validators
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import encrypted_fields.fields
import shortuuid.django_fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GoElectricRebateApplication',
            fields=[
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('id', shortuuid.django_fields.ShortUUIDField(alphabet=None, editable=False, length=16, max_length=16, prefix='', primary_key=True, serialize=False)),
                ('sin', encrypted_fields.fields.EncryptedCharField(max_length=9, validators=[api.validators.validate_sin])),
                ('status', models.CharField(choices=[('household_initiated', 'Household Initiated'), ('submitted', 'Submitted'), ('verified', 'Verified'), ('declined', 'Declined'), ('approved', 'Approved'), ('not_approved', 'Not Approved'), ('redeemed', 'Redeemed'), ('expired', 'Expired')], max_length=250)),
                ('last_name', models.CharField(max_length=250)),
                ('first_name', models.CharField(max_length=250)),
                ('middle_names', models.CharField(blank=True, max_length=250, null=True)),
                ('email', models.EmailField(max_length=250)),
                ('address', models.CharField(max_length=250)),
                ('city', models.CharField(max_length=250)),
                ('postal_code', models.CharField(blank=True, max_length=6, null=True)),
                ('drivers_licence', models.CharField(max_length=8, validators=[django.core.validators.MinLengthValidator(7)])),
                ('date_of_birth', models.DateField(validators=[api.validators.validate_driving_age])),
                ('tax_year', models.IntegerField()),
                ('doc1', models.ImageField(blank=True, null=True, upload_to='docs')),
                ('doc2', models.ImageField(blank=True, null=True, upload_to='docs')),
                ('application_type', models.CharField(max_length=25)),
                ('consent_personal', models.BooleanField(validators=[api.validators.validate_consent])),
                ('consent_tax', models.BooleanField(validators=[api.validators.validate_consent])),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'go_electric_rebate_application',
            },
        ),
        migrations.CreateModel(
            name='HouseholdMember',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('sin', encrypted_fields.fields.EncryptedCharField(max_length=9, validators=[api.validators.validate_sin])),
                ('last_name', models.CharField(max_length=250)),
                ('first_name', models.CharField(max_length=250)),
                ('middle_names', models.CharField(blank=True, max_length=250, null=True)),
                ('date_of_birth', models.DateField(validators=[api.validators.validate_driving_age])),
                ('doc1', models.ImageField(blank=True, null=True, upload_to='docs')),
                ('doc2', models.ImageField(blank=True, null=True, upload_to='docs')),
                ('consent_personal', models.BooleanField(validators=[api.validators.validate_consent])),
                ('consent_tax', models.BooleanField(validators=[api.validators.validate_consent])),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='api.goelectricrebateapplication')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'household_member',
            },
        ),
        migrations.CreateModel(
            name='GoElectricRebate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('drivers_licence', models.CharField(max_length=8, unique=True, validators=[django.core.validators.MinLengthValidator(7)])),
                ('last_name', models.CharField(max_length=250)),
                ('expiry_date', models.DateField()),
                ('rebate_max_amount', models.IntegerField(default=0)),
                ('rebate_state', models.BooleanField(default=False)),
                ('application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='api.goelectricrebateapplication')),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SubmittedGoElectricRebateApplication',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('api.goelectricrebateapplication',),
        ),
        migrations.AddConstraint(
            model_name='goelectricrebateapplication',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ['submitted', 'approved', 'redeemed', 'verified'])), fields=('drivers_licence',), name='verify_rebate_status'),
        ),
    ]
