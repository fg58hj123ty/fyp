

from flask import render_template, url_for, flash, redirect, request, Blueprint, current_app, jsonify, send_file, abort
from flask_login import login_user, current_user, logout_user, login_required

from web_app.models.models import VoiceSample, UserVoiceProfile
from web_app import db, voice_processor
from web_app.voices.utils import save_voice_sample

import os , secrets
from datetime import datetime
from werkzeug.utils import secure_filename


voices = Blueprint('voices', __name__)

def allowed_file(filename):
    """Check if the file type is allowed"""
    ALLOWED_EXTENSIONS = {'wav', 'mp3','x-wav'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@voices.route('/enroll', methods=['GET', 'POST'])
@login_required
def enroll_page():
    
    if request.method == 'POST':
        try:
            # Debug logging
            # print("Received POST request")
            # print("Form data:", request.form)
            # print("Files:", request.files)

            profile = current_user.voice_profile

            # Validate file
            if 'voice_file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            file = request.files['voice_file']

            if not file or not file.filename:
                return jsonify({'error': 'No file selected'}), 400

            if not allowed_file(file.filename):
                return jsonify({'error': 'Invalid file type. Only WAV and MP3 files are allowed'}), 400

            sample_number = request.form.get('sample_number')
            if not sample_number:
                return jsonify({'error': 'Missing sample number'}), 400

            sample_number = int(sample_number)
            if not 1 <= sample_number <= 3:
                return jsonify({'error': f'Invalid sample number: {sample_number}'}, 400)

            # Save new sample
            voice_sample = profile.add_sample(file, sample_number,'enrollment')

            

            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Voice sample uploaded successfully',
                'sample': {
                    'id': voice_sample.id,
                    'filename': voice_sample.filename,
                    'upload_date': voice_sample.date_upload.strftime('%Y-%m-%d %H:%M'),
                    'file_path': voice_sample.file_path,
                    'sample_number': voice_sample.sample_number,
                    'samples_count': profile.enrollment_samples_count
                }
            })

        except Exception as e:
            print(f"Error in enroll_page: {str(e)}")
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # GET request - render the enrollment page
    profile = current_user.voice_profile
    samples = []
    if profile:
        samples = VoiceSample.query.filter_by(profile_id=profile.id).all()
    
    return render_template('voices/enrollment.html',
                         title='Voice Sample Enrollment',
                         profile=profile,
                         samples=samples,
                         max_file_size=int(current_app.config['MAX_CONTENT_LENGTH']/1024/1024),
                         min_record_duration = int(current_app.config['MIN_RECORD_DURATION']))

@voices.route('/audio/<path:filename>')
@login_required
def serve_audio(filename):
    try:
        profile = current_user.voice_profile
        if not profile:
            return jsonify({'error': 'No profile found'}), 404

        # Sanitize filename
        filename = filename.replace('\\', '/')
        full_path = os.path.normpath(os.path.join(current_app.root_path, 'static', filename))
        static_dir = os.path.normpath(os.path.join(current_app.root_path, 'static'))
        
        # Security checks
        if not os.path.commonpath([full_path, static_dir]) == static_dir:
            return jsonify({'error': 'Invalid file path'}), 403
        
        # Verify file ownership
        if not any(sample.file_path.replace('\\', '/') == filename 
                  for sample in profile.samples if sample.file_path):
            return jsonify({'error': 'Unauthorized access'}), 403

        if not os.path.exists(full_path):
            return jsonify({'error': 'File not found'}), 404
            
        return send_file(
            full_path,
            mimetype='audio/wav' if filename.lower().endswith('.wav') else 'audio/mpeg'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@voices.route('/delete_sample', methods=['POST'])
@login_required
def delete_sample():
    try:
        # Get data from request
        data = request.get_json()
        if not data or 'sample_id' not in data:
            return jsonify({'error': 'Sample ID not provided'}), 400
        
        sample_id = data.get('sample_id')

        # Validate CSRF token
        csrf_token = request.headers.get('X-CSRFToken')
        if not csrf_token:
            return jsonify({'error': 'Invalid CSRF token'}), 403

        # Get the sample and perform validation checks
        sample = VoiceSample.query.get(sample_id)
        if not sample:
            return jsonify({'error': 'Sample not found'}), 404

        # Check if the sample belongs to the current user
        if sample.profile.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized access'}), 403

        # Get profile and sample info before deleting
        profile = sample.profile
        sample_type = sample.sample_type
        file_path = sample.file_path

        try:
            # Delete the physical file if it exists
            if file_path:
                full_path = os.path.join(current_app.root_path, 'static', file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    
            # Delete the sample from database
            db.session.delete(sample)

            # Log the activity
            profile.user.log_activity(
                'delete_sample',
                'success',
                f'Deleted sample id:{sample_id}'
            )

            # Update profile counters based on sample type
            if sample_type == 'enrollment':
                profile.enrollment_samples_count = max(0, profile.enrollment_samples_count - 1)
                profile.is_complete = profile.enrollment_samples_count >= 3

            profile.update_profile_embedding()
            
            # Commit changes
            db.session.commit()

            response_data = {
                'success': True,
                'message': 'Sample deleted successfully',
                'data': {
                    'sample_id': sample_id,
                    'sample_type': sample_type
                }
            }

            # Add enrollment-specific data if applicable
            if sample_type == 'enrollment':
                response_data['data'].update({
                    'samples_count': profile.enrollment_samples_count,
                    'is_complete': profile.is_complete
                })

            return jsonify(response_data)

        except OSError as e:
            db.session.rollback()
            return jsonify({
                'error': f'Error deleting file: {str(e)}'
            }), 500

        except Exception as e:
            # Log the failure
            profile.user.log_activity(
                'delete_sample',
                'failed',
                f'Failed to delete sample #{sample_id}: {str(e)}'
            )
            db.session.rollback()
            return jsonify({
                'error': f'Database error: {str(e)}'
            }), 500

    except Exception as e:
        return jsonify({
            'error': f'Unexpected error: {str(e)}'
        }), 500

    finally:
        try:
            db.session.close()
        except:
            pass

# @voices.route('/delete_sample/<int:sample_id>', methods=['POST'])
# @login_required
# def delete_sample(sample_id):
#     try:
#         # Validate CSRF token
#         csrf_token = request.headers.get('X-CSRFToken')
#         if not csrf_token or not current_app.config['WTF_CSRF_ENABLED']:
#             return jsonify({'error': 'Invalid CSRF token'}), 400

#         sample = VoiceSample.query.get_or_404(sample_id)
        
#         if sample.profile.user_id != current_user.id:
#             return jsonify({'error': 'Unauthorized access'}), 403

#         # Delete file
#         if sample.file_path:
#             full_path = os.path.join(current_app.root_path, 'static', sample.file_path)
#             if os.path.exists(full_path):
#                 os.remove(full_path)

#         # Update profile
#         profile = sample.profile
#         profile.enrollment_samples_count -= 1
#         profile.is_complete = profile.enrollment_samples_count >= 3

#         db.session.delete(sample)
#         db.session.commit()

#         return jsonify({
#             'success': True,
#             'message': 'Sample deleted successfully',
#             'samples_count': profile.enrollment_samples_count
#         })

#     except Exception as e:
#         db.session.rollback()
#         return jsonify({'error': str(e)}), 500

@voices.route('/verify', methods=['GET', 'POST'])
@login_required
def verify_page():
    
    profile = current_user.voice_profile
    
    # Get next available id
    last_id = VoiceSample.query.filter_by(
        profile_id = profile.id
        ).order_by(VoiceSample.id.desc()).first()

    next_id = 1 if not last_id else last_id.id +1

    if request.method == 'POST':

        # print("Received POST request")
        # print("Form data:", request.form)
        # print("Files:", request.files)
        
        if 'voice_file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['voice_file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        try:

            # Save the new sample
            verification_sample = profile.add_sample(file, next_id, 'verify')

            db.session.commit()
        
            
            return jsonify({
                'success': True,
                'message': 'Sample saved successfully',
                'sample_id': verification_sample.id,
                'sample_type': verification_sample.sample_type,
                'file_path': verification_sample.file_path
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    
    # Get all enrollment samples for this user
    enrollment_results = VoiceSample.query.filter_by(
        profile_id=current_user.voice_profile.id,
        sample_type='enrollment'
    ).order_by(VoiceSample.sample_number.asc()).all()

    # Get all verification samples for this user
    verification_samples = VoiceSample.query.filter_by(
        profile_id=current_user.voice_profile.id,
        sample_type='verify'
    ).order_by(VoiceSample.sample_number).all()

    
    
    
    return render_template('voices/verification.html',
                        title='User Verification',
                        enrollment_results = enrollment_results,
                        verification_samples = verification_samples,
                        next_id = next_id,
                        profile=profile,
                        access_code=current_user.access_code,
                        min_record_duration=int(current_app.config['MIN_RECORD_DURATION']),
                        max_file_size=int(current_app.config['MAX_CONTENT_LENGTH']/1024/1024))


@voices.route('/get_verification_samples', methods=['GET'])
@login_required
def get_verification_samples():
    try:
        # Get verification samples for the current user
        samples = VoiceSample.query.filter_by(
            profile_id=current_user.voice_profile.id,
            sample_type='verify'
        ).order_by(VoiceSample.sample_number).all()
        
        # Convert samples to JSON-serializable format
        samples_data = [{
            'id': sample.id,
            'file_path': sample.file_path,
            'date_upload': sample.date_upload.isoformat()
        } for sample in samples]
        
        return jsonify({
            'success': True,
            'samples': samples_data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    


@voices.route('/get_similarity', methods=['POST'])
@login_required

def get_similarity():
    try:
        data = request.get_json()
        sample_id = data.get('sampleId')

        enrollment_samples = VoiceSample.query.filter_by(
            profile_id = current_user.voice_profile.id,
            sample_type='enrollment'
        ).all()

        verification_sample = VoiceSample.query.filter_by(
            profile_id = current_user.voice_profile.id,
            sample_type='verify',
            id=sample_id
        ).first()

        

        verification_embedding = verification_sample.get_embedding()

        profile_embedding = current_user.voice_profile.get_profile_embedding()
        avg_embedding = voice_processor.compare_embeddings(verification_embedding, profile_embedding)

        results = []
        for sample in enrollment_samples:
            similarity_result = voice_processor.compare_embeddings(verification_embedding, sample.get_embedding())
            results.append({
                'sample_id': sample.id,
                'similarity': similarity_result[0]
                })


        return jsonify({
            'success': True,
            'similarity_results': results,
            'avg_embedding': avg_embedding
        })
    except Exception as e:
        print(f"Error in get_similarity: {str(e)}")  
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
        

        