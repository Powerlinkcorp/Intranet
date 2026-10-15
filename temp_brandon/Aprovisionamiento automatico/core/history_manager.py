# -*- coding: utf-8 -*-
from .services.history_service import HistoryService

log_provision = HistoryService.log
get_recent_history = HistoryService.get_recent
get_export_file = HistoryService.get_export_file
