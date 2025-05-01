from datetime import datetime
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from web_app import db, login_manager
from flask_login import UserMixin
from sqlalchemy import event
import json, os
import numpy as np

from web_app.voices.utils import save_voice_sample

from .mixins import DateFormatterMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



class User(db.Model, UserMixin, DateFormatterMixin):

    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    username = db.Column(db.String(20), unique=True, nullable=False)
    alias = db.Column(db.String(50))
    access_code = db.Column(db.Integer)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    date_join = db.Column(db.DateTime, nullable=False, default = datetime.utcnow)

    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    # voice_samples = db.relationship('VoiceSample', backref='user', lazy=True)
    voice_profile = db.relationship('UserVoiceProfile', backref='user', uselist=False, cascade='all, delete-orphan')

    voice_samples = db.relationship('VoiceSample', backref='user',
                                    secondary='user_voice_profile',
                                    viewonly=True)


    def log_activity(self, activity_type, status, details=None):
        activity = ActivityLog(
            user_id=self.id,
            activity_type=activity_type,
            status=status,
            details=details
        )
        db.session.add(activity)
        db.session.commit()

    def get_recent_activities(self, limit=10):
        return ActivityLog.query.filter_by(user_id=self.id)\
            .order_by(ActivityLog.timestamp.desc())\
            .limit(limit).all()
    
    @property
    def last_login(self):
        return ActivityLog.query.filter_by(
            user_id=self.id,
            activity_type='login'
        ).order_by(ActivityLog.timestamp.desc()).first()

    @property
    def last_verification(self):
        return ActivityLog.query.filter_by(
            user_id=self.id,
            activity_type='verification'
        ).order_by(ActivityLog.timestamp.desc()).first()

    def get_verification_stats(self):
        verifications = ActivityLog.query.filter_by(
            user_id=self.id,
            activity_type='verification'
        ).all()
        
        total = len(verifications)
        if total == 0:
            return 0, 0
        
        successful = len([v for v in verifications if v.status == 'success'])
        success_rate = (successful / total) * 100
        
        return success_rate, total
    


    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id':self.id})
    
    
    @staticmethod
    def verify_reset_token(token):

        s = Serializer(current_app.config['SECRET_KEY'])

        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        
        return User.query.get(user_id)
    
    @property
    def has_complete_voice_profile(self):
        return self.voice_profile is not None and self.voice_profile.is_complete
    
    @property
    def remaining_voice_samples(self):
        if self.voice_profile is None:
            return 3
        return 3 - self.voice_profile.enrollment_samples_count
    
    def __repr__(self):
        return f"User('{self.username}', '{self.email}, '{self.date_join}', '{self.alias}')"

class VoiceSample(db.Model, DateFormatterMixin):

    __tablename__ = 'voice_sample'

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('user_voice_profile.id'), nullable=False)
    filename = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    date_upload = db.Column(db.DateTime, nullable=False, default = datetime.utcnow)

    # samples metadata
    sample_number = db.Column(db.Integer, nullable=False)
    sample_duration = db.Column(db.Float)
    sample_size = db.Column(db.Integer)
    sample_format = db.Column(db.String(10))
    sample_quality_score = db.Column(db.Float)

    # sample type (enrollment or verification)
    sample_type = db.Column(db.String(20), nullable=False)

    embedding = db.Column(db.LargeBinary, default=None, nullable=True)


    def set_embedding(self,embedding_array):
        # Convert numpy array to binary
        
        self.embedding = embedding_array.tobytes()

    def get_embedding(self):
        # Convert binary back to numpy array

        if self.embedding is not None:
            return np.frombuffer(self.embedding, dtype=np.float32)
        return None

    def __repr__(self):
        embedding_size = len(self.embedding) if self.embedding is not None else 0
        return f"VoiceSample(id={self.id}, type={self.sample_type}, profile_id={self.profile_id}, sample_number={self.sample_number}, embedding_size={embedding_size})"


class UserVoiceProfile(db.Model, DateFormatterMixin):

    __tablename__ = 'user_voice_profile'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_create = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_update = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Profile status
    is_complete = db.Column(db.Boolean, default=False, nullable=False)
    enrollment_samples_count = db.Column(db.Integer, default=0, nullable=False)
    profile_embedding = db.Column(db.LargeBinary, default=None, nullable=True)

    # Verification settings
    verification_threshold = db.Column(db.Float, default=0.7)

    # Relationships
    samples = db.relationship('VoiceSample', backref='profile', cascade='all, delete-orphan')
    # user = db.relationship('User', backref=db.backref('voice_profile',uselist=False))
  

    def add_sample(self, file, sample_number, sample_type):
        """Add a new voice sample to the profile"""
        try:
            # Save file and get details
            file_details = save_voice_sample(file, self.user_id)
            
            # Create new sample
            sample = VoiceSample(
                profile_id=self.id,
                filename=file_details['filename'],
                file_path=file_details['file_path'],
                sample_type=sample_type,
                sample_number=sample_number,
                sample_size=file_details.get('file_size'),
                sample_format=file_details.get('file_format'),
                sample_duration=file_details.get('file_duration'),
                embedding=file_details['embedding']
            )
            
            # Add to session
            db.session.add(sample)
            
            # Update profile status
            if sample.sample_type == 'enrollment' :
                self.enrollment_samples_count += 1
                self.is_complete = self.enrollment_samples_count >= 3
                self.last_update = datetime.utcnow()

                # Update profile embedding if we have all required samples
                
            self.update_profile_embedding()

            self.user.log_activity(
            'enroll',
            'success',
            f'Added {sample_type} sample id:{sample.id}'
        )
            
            return sample
            
        except Exception as e:
            self.user.log_activity(
            'enroll',
            'failed',
            f'Failed to add {sample_type} sample #{sample_number}: {str(e)}'
        )
            db.session.rollback()
            raise ValueError(f"Failed to add voice sample: {str(e)}")
        
    def delete_sample(self, sample_number):
        """Delete a specific sample"""
        try:
            sample = VoiceSample.query.filter_by(
                profile_id=self.id,
                sample_number=sample_number
            ).first()
            
            if sample:
                # Delete file if exists
                if sample.file_path:
                    full_path = os.path.join(current_app.config['STATIC_FOLDER'], sample.file_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                
                # Update profile status
                self.enrollment_samples_count -= 1
                self.is_complete = self.enrollment_samples_count >= 3
                
                # Remove from database
                db.session.delete(sample)
                
            return True
            
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Failed to delete sample: {str(e)}")
        
    def cal_average_embeddings(self,embeddings):
        """ Process multiple audio samples and return averaged embedding """
        
        if not embeddings or len(embeddings) == 0:
            return None
    
        stacked_embeddings = np.stack(embeddings)

        average_embedding = np.mean(stacked_embeddings, axis=0)

        # Normalize
        norm = np.linalg.norm(average_embedding)
        if norm > 0:  # Avoid division by zero
            average_embedding = average_embedding / norm
            
        return average_embedding
    
    def set_profile_embedding(self, embedding_array):
        """Convert numpy array to bytes and store"""
        if embedding_array is not None:
            self.profile_embedding = embedding_array.tobytes()
        else:
            self.profile_embedding = None

    def get_profile_embedding(self):
        """Convert bytes back to numpy array"""
        if self.profile_embedding:
            return np.frombuffer(self.profile_embedding, dtype=np.float32)
        return None

    def update_profile_embedding(self):
        """Update the profile's average embedding using enrollment samples"""
        try:
            # Get embeddings from enrollment samples
            samples = self.get_enrollment_samples()
            
            embeddings = []

            for sample in samples:
                embedding = sample.get_embedding()
                if embedding is not None and embedding.size > 0:  
                    embeddings.append(embedding)
            
            if len(embeddings) >= 3:  # Ensure we have at least 3 samples
                # Calculate average embedding
                avg_embedding = self.cal_average_embeddings(embeddings)
                
                if avg_embedding is not None and avg_embedding.size > 0:
                    # Update profile embedding in database
                    self.set_profile_embedding(avg_embedding)
                    self.last_update = datetime.utcnow()
                    db.session.commit()
                    return True
            else:
                # Clear embedding if profile is not complete
                self.set_profile_embedding(None)
                self.last_update = datetime.utcnow()
                db.session.commit()
            
            return False
            
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Failed to update profile embedding: {str(e)}")


    
    def get_enrollment_samples(self):
        """ Get all enrollment samples"""
        return [s for s in self.samples if s.sample_type == 'enrollment']
    
    def get_verification_samples(self):
        """ Get all verification samples """
        return [s for s in self.samples if s.sample_type == ' verification']
    
    def get_sample_embeddings(self, sample_type='enrollment'):
        """Get embeddings for all samples of specified type"""
        samples = self.get_enrollment_samples() if sample_type == 'enrollment' else self.get_verification_samples()
        embeddings = []
        
        for sample in samples:
            embedding = sample.get_embedding()
            if embedding is not None:
                embeddings.append({
                    'sample_number': sample.sample_number,
                    'embedding': embedding
                })
                
        return embeddings

    def __repr__(self):
        return f"UserVoiceProfile(user_id={self.user_id}, samples={self.enrollment_samples_count}, complete={self.is_complete})"

class ActivityLog(db.Model, DateFormatterMixin):
    __tablename__ = 'activity_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activity_type = db.Column(db.String(50), nullable=False)  # 'verification', 'enrollment', 'login', etc.
    status = db.Column(db.String(20), nullable=False)  # 'success', 'failed', 'pending'
    details = db.Column(db.String(255))

    # Relationship
    user = db.relationship('User', backref=db.backref('activities', lazy=True))

    def __repr__(self):
        return f"ActivityLog(user_id={self.user_id}, type={self.activity_type}, status={self.status})"


@event.listens_for(User, 'after_insert')
def create_user_voice_profile(mapper, connection, user):

    now = datetime.utcnow()

    # create a new voice profile
    voice_profile = UserVoiceProfile.__table__.insert().values(
        user_id = user.id,
        is_complete=False,
        enrollment_samples_count = 0,
        date_create = now,
        last_update = now
    )
    
    # Execute the insert
    connection.execute(voice_profile)


