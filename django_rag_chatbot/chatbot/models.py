from django.db import models

class Document(models.Model):
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='documents/', null=True, blank=True)
    text_content = models.TextField(null=True, blank=True)  # 직접 입력한 텍스트
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    chunk_count = models.IntegerField(default=0)
    
    def __str__(self):
        return self.title