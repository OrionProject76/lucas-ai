import vision_manager

def main():
    vm = vision_manager.VisionManager()
    description = vm.see_and_describe()
    if description:
        print(description)
    else:
        print("Aucune description disponible.")

if __name__ == "__main__":
    main()
