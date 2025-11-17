#!/usr/bin/env python
"""
데이터베이스 초기화 스크립트
기존 app.db를 삭제하고 새로운 스키마로 재생성합니다.
"""
import os
import sys

# app.py와 같은 디렉토리에서 실행된다고 가정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def init_database():
    """데이터베이스 초기화"""
    # app context에서 실행
    with app.app_context():
        # 기존 테이블 삭제
        print("기존 테이블 삭제 중...")
        db.drop_all()

        # 새 테이블 생성
        print("새로운 테이블 생성 중...")
        db.create_all()

        print("✓ 데이터베이스 초기화 완료!")
        print("  위치: instance/app.db")

if __name__ == '__main__':
    init_database()
