import cv2

# 0 points to your built-in Mac webcam
cap = cv2.VideoCapture(0)

if not cap.isOpened():
  print(
      "Error: Could not open camera. Check Mac System Settings -> Privacy &"
      " Security -> Camera permissions for Terminal/VS Code."
  )
else:
  print("Camera started successfully! Press 'q' in the video window to quit.")
  while True:
    ret, frame = cap.read()
    if not ret:
      print("Failed to grab frame.")
      break

    # Display the live feed in a window
    cv2.imshow("Mac Webcam Test", frame)

    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord("q"):
      break

  cap.release()
  cv2.destroyAllWindows()