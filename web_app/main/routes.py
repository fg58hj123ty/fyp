
from flask import render_template, request, Blueprint
from web_app.models.models import User, VoiceSample, UserVoiceProfile, ActivityLog
from flask_login import current_user, login_required
from datetime import datetime, timedelta

from datetime import datetime

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/home')
def home():
    return render_template('main/home.html',
                           title = 'home')


@main.route('/about')
def about():
    return render_template('main/about.html',
                            title = 'About')

@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        # Admin dashboard logic
        now = datetime.utcnow()
        last_24h = now - timedelta(days=1)
        
        # Get verification statistics
        verifications = ActivityLog.query.filter_by(
            activity_type='verification'
        ).all()
        
        total_verifications = len(verifications)
        successful_verifications = sum(1 for v in verifications if v.status == 'success')
        failed_verifications = total_verifications - successful_verifications
        
        success_rate = round((successful_verifications / total_verifications * 100), 1) if total_verifications > 0 else 0
        fail_rate = round((failed_verifications / total_verifications * 100), 1) if total_verifications > 0 else 0
        
        stats = {
            'total_users': User.query.count(),
            'active_users': User.query.join(ActivityLog).filter(
                ActivityLog.timestamp > last_24h
            ).distinct().count(),
            
            'total_verifications': total_verifications,
            'success_rate': success_rate,
            'fail_rate': fail_rate,
            
            'last_update': now.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Get paginated activity log
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filter parameters
        activity_type = request.args.get('activity_type')
        status = request.args.get('status')
        user_id = request.args.get('user_id', type=int)
        
        # Build query
        query = ActivityLog.query
        
        if activity_type:
            query = query.filter_by(activity_type=activity_type)
        if status:
            query = query.filter_by(status=status)
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        # Get activities with pagination
        activities = query.order_by(ActivityLog.timestamp.desc()).paginate(
            page=page, per_page=per_page
        )
        
        # Get unique users for filter dropdown
        users = User.query.all()
        
        return render_template(
            'main/dashboard.html',
            stats=stats,
            activities=activities,
            users=users,
            selected_type=activity_type,
            selected_status=status,
            selected_user=user_id,
            title='Admin Dashboard'
        )
    
    else:
        # User dashboard logic
        success_rate, total_attempts = current_user.get_verification_stats()
        
        last_login_time = "Never"
        if current_user.last_login:
            last_login_time = current_user.last_login.format_timestamp()
        
        last_verification_time = "Never"
        if current_user.last_verification:
            last_verification_time = current_user.last_verification.timestamp.strftime('%Y-%m-%d %H:%M')
        
        activities = current_user.get_recent_activities()
        
        return render_template(
            'main/dashboard.html',
            success_rate=success_rate,
            total_attempts=total_attempts,
            last_login_time=last_login_time,
            last_verification_time=last_verification_time,
            activities=activities,
            title='Dashboard'
        )

# Add template filters for badges
@main.app_template_filter('activity_badge')
def activity_badge_filter(activity_type):
    badges = {
        'verification': 'primary',
        'enrollment': 'success',
        'login': 'info',
        'profile_update': 'warning'
    }
    return badges.get(activity_type, 'secondary')

@main.app_template_filter('status_badge')
def status_badge_filter(status):
    badges = {
        'success': 'success',
        'failed': 'danger',
        'pending': 'warning'
    }
    return badges.get(status, 'secondary')

# @main.route('/debug/db')
# def debug_database():

#     data = {
#         'users': [],
#         'voices': [],
#         'profiles': []
#     }
    
#     # Get all users
#     users = User.query.all()
#     for user in users:
#         user_data = {
#             'id': user.id,
#             'username': user.username,
#             'email': user.email,
#             'image_file': user.image_file,
#             'date_join': user.format_date_join() if hasattr(user, 'date_join') else None
#         }
#         data['users'].append(user_data)

#     # Get all voices
#     voices = VoiceSample.query.all()
    
#     for voice in voices:
#         # embedding = voice.set_embedding(voice.embedding)
#         voice_data = {
#             'id': voice.id,
#             'profile_id':voice.profile_id,
#             'filename': voice.filename,
#             'filepath': voice.file_path,
#             'sample_type': voice.sample_type,
#             'embedding':voice.get_embedding(),
#             'date_upload': voice.format_date_upload() if hasattr(voice, 'date_upload') else None
#         }
#         data['voices'].append(voice_data)

#     # Get all profiles
#     profiles = UserVoiceProfile.query.all()

#     for profile in profiles:
#         profile_data = {
#             'id': profile.id,
#             'user_id': profile.user_id,
#             'date_create': profile.format_date_create(),
#             'last_update': profile.format_last_update(),
#             'enrollment_samples_count': profile.enrollment_samples_count,
#             'is_complete': profile.is_complete,
#             'embedding':profile.get_profile_embedding()
#         }
#         data['profiles'].append(profile_data)
    

    
#     return render_template('db.html', data=data, hide_right_nav = True)

@main.route('/debug/db')
def debug_database():
    data = {
        'users': [],
        'voices': [],
        'profiles': []
    }
    
    # Get all users
    users = User.query.all()
    for user in users:
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'alias': user.alias,
            'is_admin': user.is_admin,
            'access_code': user.access_code,
            'image_file': user.image_file,
            'date_join': user.format_date_join()  # Use the mixin method
        }
        data['users'].append(user_data)

    # Get all profiles
    profiles = UserVoiceProfile.query.all()
    for profile in profiles:
        user = User.query.get(profile.user_id)
        profile_data = {
            'id': profile.id,
            'user_id': profile.user_id,
            'username': user.username if user else 'N/A',
            'date_create': profile.format_date_create(),  # Use the mixin method
            'last_update': profile.format_last_update(),  # Use the mixin method
            'enrollment_samples_count': profile.enrollment_samples_count,
            'is_complete': profile.is_complete,
            'verification_threshold': profile.verification_threshold,
            'embedding': profile.get_profile_embedding()
        }
        data['profiles'].append(profile_data)

    # Get all voices
    voices = VoiceSample.query.all()
    for voice in voices:
        profile = UserVoiceProfile.query.get(voice.profile_id)
        user = User.query.get(profile.user_id) if profile else None
        
        voice_data = {
            'id': voice.id,
            'profile_id': voice.profile_id,
            'username': user.username if user else 'N/A',
            'filename': voice.filename,
            'file_path': voice.file_path,
            'sample_type': voice.sample_type,
            'sample_number': voice.sample_number,
            'sample_duration': voice.sample_duration,
            'sample_size': voice.sample_size,
            'sample_format': voice.sample_format,
            'sample_quality_score': voice.sample_quality_score,
            'embedding': voice.get_embedding(),
            'date_upload': voice.format_date_upload()  # Use the mixin method
        }
        data['voices'].append(voice_data)
    
    return render_template('db.html', data=data, hide_right_nav=True)