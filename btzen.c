#include <stdio.h>
#include <stdlib.h>
#include <systemd/sd-bus.h>

typedef struct {
    char *chr_data;
    char *chr_conf;
    char *chr_period;
    uint8_t *data;
    size_t len;
} t_bt_device;

typedef struct bt_device_chr {
    char *path;
    char *uuid;
    struct bt_device_chr *next;
} t_bt_device_chr;

static t_bt_device *last_device = NULL;

t_bt_device *bt_device_last(void) {
    t_bt_device *dev = last_device;
    last_device = NULL;
    return dev;
}

int bt_device_connect(sd_bus *bus, const char *path) {
    int r;
    sd_bus_message *m = NULL;
    sd_bus_error error = SD_BUS_ERROR_NULL;

    r = sd_bus_call_method(
        bus,
        "org.bluez",
        path,
        "org.bluez.Device1",
        "Connect",
        &error,
        &m,
        NULL
    );
    if (r < 0) {
        fprintf(stderr, "Failed to issue method call: %s\n", error.message);
        sd_bus_error_free(&error);
    }
    sd_bus_message_unref(m);

/*
    r = sd_bus_call_method(
        bus,
        "org.bluez",
        "/org/bluez/hci0",
        "org.bluez.Adapter1",
        "StartDiscovery",
        &error,
        &m,
        NULL
    );
    if (r < 0) {
        fprintf(stderr, "Failed to issue method call: %s\n", error.message);
        sd_bus_error_free(&error);
    }
    sd_bus_message_unref(m);
*/
    return r;
}

int bt_device_is_connected(sd_bus *bus, const char *mac) {
    return 0;
}

int bt_device_write(sd_bus *bus, t_bt_device *dev) {
    int r;
    sd_bus_message *m = NULL;
    sd_bus_message *reply = NULL;
    sd_bus_error error = SD_BUS_ERROR_NULL;

    r = sd_bus_message_new_method_call(
        bus,
        &m,
        "org.bluez",
        dev->chr_conf,
        "org.bluez.GattCharacteristic1",
        "WriteValue"
    );
    if (r < 0) {
        fprintf(stderr, "Failed to create call to WriteValue\n");
        goto finish;
    }

    sd_bus_message_append_array(m, 'y', (unsigned char[]){1}, 1);
    sd_bus_message_open_container(m, 'a', "{sv}");
    sd_bus_message_close_container(m);

    r = sd_bus_call(bus, m, 0, &error, &reply);
    if (r < 0) {
        fprintf(stderr, "Failed to call WriteValue: %s\n", error.message);
        goto finish;
    }
finish:
    sd_bus_error_free(&error);
    sd_bus_message_unref(m);
    sd_bus_message_unref(reply);
    return r;
}

int bt_device_read(sd_bus *bus, uint8_t data[]) {
    int r;
    size_t len;
    const void *buff;
    sd_bus_message *m = NULL;
    sd_bus_error error = SD_BUS_ERROR_NULL;


    r = sd_bus_call_method(
        bus,
        "org.bluez",
        "/org/bluez/hci0/dev_B0_B4_48_BD_04_06/service001f/char0020",
        "org.bluez.GattCharacteristic1",
        "ReadValue",
        &error,
        &m,
        "a{sv}",
        NULL
    );
    if (r < 0) {
        fprintf(stderr, "Failed to issue ReadValue call: %s\n", error.message);
        goto finish;
    }

    r = sd_bus_message_read_array(m, 'y', &buff, &len);
    if (r < 0) {
        fprintf(stderr, "Failed to retrieve ReadValue data: %s\n", strerror(-r));
        goto finish;
    }

    memcpy(data, buff, len);

finish:
    sd_bus_error_free(&error);
    sd_bus_message_unref(m);
    return r;
}

static int bt_device_data(sd_bus_message *m, void *user_data, sd_bus_error *error) {
    int r;
    size_t len;
    const void *buff;
    t_bt_device *dev = user_data;
    
    r = sd_bus_message_read_array(m, 'y', &buff, &len);
    if (r < 0) {
        fprintf(stderr, "Failed to parse response message: %s\n", strerror(-r));
        return r;
    }

    memcpy(dev->data, buff, dev->len);
    last_device = dev;
    return 0;
}


int bt_device_read_async(sd_bus *bus, t_bt_device *dev) {
    int r;

    r = sd_bus_call_method_async(
        bus,
        NULL,
        "org.bluez",
        dev->chr_data,
        "org.bluez.GattCharacteristic1",
        "ReadValue",
        bt_device_data,
        dev,
        "a{sv}",
        NULL
    );
    if (r < 0)
        fprintf(stderr, "Failed to create async ReadValue call\n");

    return r;
}

int bt_device_chr_uuid(sd_bus *bus, const char *path, const char **uuid) {
    int r;
    sd_bus_message *m = NULL;
    sd_bus_error error = SD_BUS_ERROR_NULL;

    r = sd_bus_get_property(
        bus,
        "org.bluez",
        path,
        "org.bluez.GattCharacteristic1",
        "UUID",
        &error,
        &m,
        "s"
    );
    if (r < 0) {
        fprintf(stderr, "Failed to read UUID property: %s\n", error.message);
        goto finish;
    }

    r = sd_bus_message_read(m, "s", uuid);
    if (r < 0) {
        fprintf(stderr, "Failed to get UUID property data: %s\n", error.message);
        goto finish;
    }

finish:
    sd_bus_message_unref(m);
    sd_bus_error_free(&error);
    return r;
}

int bt_device_chr_list(sd_bus *bus, t_bt_device_chr **root) {
    int r;
    int len;
    sd_bus_message *m = NULL;
    sd_bus_error error = SD_BUS_ERROR_NULL;
    t_bt_device_chr *current = NULL;
    t_bt_device_chr *prev = NULL;
    const char *path;
    const char *uuid;

    r = sd_bus_call_method(
        bus,
        "org.bluez",
        "/",
        "org.freedesktop.DBus.ObjectManager",
        "GetManagedObjects",
        &error,
        &m,
        NULL
    );
    if (r < 0) {
        fprintf(stderr, "Failed to issue method call: %s\n", error.message);
        goto finish;
    }

    sd_bus_message_enter_container(m, SD_BUS_TYPE_ARRAY, "{oa{sa{sv}}}");
    if (r < 0) {
        fprintf(stderr, "GetManagedObjects interface error\n");
        goto finish;
    }

    while ((r = sd_bus_message_enter_container(m, SD_BUS_TYPE_DICT_ENTRY, "oa{sa{sv}}")) > 0) {
        sd_bus_message_read(m, "o", &path);
        sd_bus_message_enter_container(m, SD_BUS_TYPE_ARRAY, "{sa{sv}}");

        while ((r = sd_bus_message_enter_container(m, SD_BUS_TYPE_DICT_ENTRY, "sa{sv}")) > 0) {
            const char *iface;

            r = sd_bus_message_read(m, "s", &iface);
            sd_bus_message_skip(m, "a{sv}");

            if (!strcmp(iface, "org.bluez.GattCharacteristic1")) {
                bt_device_chr_uuid(bus, path, &uuid);

                /* create linked list of t_bt_device_chr records */
                prev = current;
                current = malloc(sizeof(t_bt_device_chr));

                len = strlen(path) + 1;
                current->path = malloc(len);
                strncpy(current->path, path, len);
                current->path[len - 1] = '\0';

                len = strlen(uuid) + 1;
                current->uuid = malloc(len);
                strncpy(current->uuid, uuid, len);
                current->uuid[len - 1] = '\0';

                current->next = NULL;
                if (prev != NULL)
                    prev->next = current;

                if (*root == NULL)
                    *root = current;
            }
            sd_bus_message_exit_container(m);
        }
        sd_bus_message_exit_container(m); /* array */
        sd_bus_message_exit_container(m); /* dict entry */
    }
    sd_bus_message_exit_container(m); /* array */

finish:
    sd_bus_message_unref(m);
    sd_bus_error_free(&error);
    return r;
}

void bt_device_chr_list_free(t_bt_device_chr *root) {
    t_bt_device_chr *curr = root;
    t_bt_device_chr *next;
    while (curr) {
        next = curr->next;
        free(curr->path);
        free(curr->uuid);
        free(curr);
        curr = next;
    }
}

/* vim: sw=4:et:ai
 */
