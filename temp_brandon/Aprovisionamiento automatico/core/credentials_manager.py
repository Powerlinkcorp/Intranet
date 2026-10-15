# -*- coding: utf-8 -*-
from .services.credentials_service import CredentialsService

load_credentials = CredentialsService.load
save_credentials = CredentialsService.save
get_candidates = CredentialsService.get_candidates
