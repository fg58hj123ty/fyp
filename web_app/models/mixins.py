


from datetime import datetime
import pytz


class DateFormatterMixin:
    def format_date(self,date_field):
        """ Format a datetime field to UTC+8 string """
        if not hasattr(self,date_field) or getattr(self,date_field) is None:
            return ""
        
        dt = getattr(self, date_field)
        utc_dt = dt.replace(tzinfo=pytz.UTC)
        hk_tz = pytz.timezone('Asia/Hong_Kong')
        hk_dt = utc_dt.astimezone(hk_tz)
        return hk_dt.strftime('%Y-%m-%d %H:%M')
    
    def format_date_join(self):
        return self.format_date('date_join')
    
    def format_date_create(self):
        return self.format_date('date_create')
    
    def format_date_upload(self):
        return self.format_date('date_upload')
    
    def format_last_update(self):
        return self.format_date('last_update')
    
    def format_timestamp(self):
        return self.format_date('timestamp')